import pandas as pd
import numpy as np
import json
import os
import re
import shutil
import unicodedata
from openpyxl import load_workbook

from backend.common.excel_io import lire_feuille_wide, extraire_poids  # import direct


def fichier_de_travail(nom_fichier: str) -> str:
    """
    Retourne le chemin du fichier de calculs (data/processed/) et le cree a
    partir du fichier source s'il n'existe pas encore.

    Le fichier de travail n'est jamais ecrase s'il existe deja : il contient
    des feuilles (ex. 'core') absentes du fichier brut.
    """
    from config.settings import FICHIER_DONNEES_CALCULS

    fichier_calculs = str(FICHIER_DONNEES_CALCULS)
    os.makedirs(os.path.dirname(fichier_calculs), exist_ok=True)
    if not os.path.exists(fichier_calculs):
        shutil.copyfile(nom_fichier, fichier_calculs)
    return fichier_calculs


def extraire_toutes_categories(d):
    """Extrait récursivement toutes les clés terminales d'un dict JSON hiérarchique."""
    result = set()
    if isinstance(d, dict):
        for k, v in d.items():
            result.add(k)
            result |= extraire_toutes_categories(v)
    elif isinstance(d, list):
        for v in d:
            result |= extraire_toutes_categories(v)
    return result


def calculer_ipc(nom_fichier: str, feuille: str, date_debut: str, date_fin: str):
    """
    Calcule l'IPC global d'un panier en utilisant les poids de config/weights.json
    et insère/réécrit les résultats dans une colonne fixe 'IPC (%)'.
    """

    # --- Charger la feuille en wide
    df = lire_feuille_wide(nom_fichier, feuille)

    # --- S'assurer que la colonne 'date' est bien au format YYYY-MM
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.to_period("M")
        df.set_index("date", inplace=True)
    else:
        df.index = pd.to_datetime(df.index).to_period("M")

    # --- Transformer les arguments en période mensuelle
    date_debut = pd.Period(date_debut, freq="M")
    date_fin = pd.Period(date_fin, freq="M")

    # --- Filtrer la période
    df = df.loc[date_debut:date_fin]

    # --- Charger les poids
    from config.settings import BASE_DIR

    CONFIG_PATH = BASE_DIR / "config" / "weights.json"

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        all_weights = json.load(f)

    poids_feuille = extraire_poids(all_weights.get(feuille, {}))

    if not poids_feuille:
        raise ValueError(f"Aucun poids trouvé pour la feuille {feuille} dans weights.json")

    colonnes_valides = [col for col in df.columns if col in poids_feuille]
    if not colonnes_valides:
        raise ValueError("Aucune correspondance entre colonnes du fichier Excel et weights.json")

    # --- Calcul de l’IPC (moyenne pondérée)
    numerateur = sum(df[col] * poids_feuille[col] for col in colonnes_valides)
    denominateur = sum(poids_feuille[col] for col in colonnes_valides)

    # Précision volontairement large (pas 2 décimales) : cette colonne sert
    # d'entrée à l'inflation MoM/YoY (calculer_inflation_mom/yoy). Arrondir
    # ici à 2 décimales avant de recalculer un taux de croissance décalait
    # l'inflation affichée de 0.01 à 0.05 point vs la référence officielle
    # (double arrondi). L'arrondi à 2 décimales n'a de sens qu'à l'affichage.
    df["IPC (%)"] = (numerateur / denominateur).round(6)

    # --- Insérer dans Excel avec openpyxl en réécrivant toujours dans 'IPC (%)'
    wb = load_workbook(nom_fichier)
    ws = wb[feuille]

    # Trouver ou créer la colonne "IPC (%)"
    header_row = 1
    col_index_ipc = None
    for col in range(1, ws.max_column + 1):
        if ws.cell(row=header_row, column=col).value == "IPC (%)":
            col_index_ipc = col
            break

    if col_index_ipc is None:
        col_index_ipc = ws.max_column + 1
        ws.cell(row=header_row, column=col_index_ipc, value="IPC (%)")

    # Construire un dictionnaire {periode: valeur}
    ipc_dict = df["IPC (%)"].to_dict()

    # Écrire les valeurs au bon endroit
    for row in range(2, ws.max_row + 1):
        cell_date = ws.cell(row=row, column=1).value  # on suppose la date est en première colonne
        if cell_date is None:
            continue

        try:
            periode = pd.to_datetime(cell_date).to_period("M")
        except Exception:
            continue

        if periode in ipc_dict:
            ws.cell(row=row, column=col_index_ipc, value=float(ipc_dict[periode]))

    wb.save(nom_fichier)
    wb.close()

    return df


def calculer_ipc_core_noncore(
    nom_fichier: str, feuille_core: str, feuille_non_core: str, date_debut: str, date_fin: str
):
    """
    Calcule l'IPC core et l'IPC non-core et les insère dans les colonnes
    'IPC Core (%)' et 'IPC Non Core (%)' des feuilles correspondantes.
    Si la colonne existe déjà, elle est réécrite (pas de nouvelle colonne ajoutée).
    """

    # --- Charger config/weights.json ---
    from config.settings import BASE_DIR

    CONFIG_PATH = BASE_DIR / "config" / "weights.json"

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        all_weights = json.load(f)

    # --------------------------------------------------
    # Fonction interne pour calculer et insérer un IPC
    # --------------------------------------------------
    def traiter_feuille(feuille: str, nom_colonne: str):
        # Lire feuille wide
        df = lire_feuille_wide(nom_fichier, feuille)

        # Normaliser les dates
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.to_period("M")
            df.set_index("date", inplace=True)
        else:
            df.index = pd.to_datetime(df.index).to_period("M")

        # Filtrer période
        d_debut = pd.Period(date_debut, freq="M")
        d_fin = pd.Period(date_fin, freq="M")
        df = df.loc[d_debut:d_fin]

        # Extraire les poids
        poids_feuille = extraire_poids(all_weights.get(feuille, {}))
        if not poids_feuille:
            raise ValueError(f"Aucun poids trouvé pour la feuille {feuille} dans weights.json")

        # Colonnes valides
        colonnes_valides = [col for col in df.columns if col in poids_feuille]
        if not colonnes_valides:
            raise ValueError(f"Aucune correspondance entre colonnes Excel et poids pour {feuille}")

        # Calcul IPC pondéré
        numerateur = sum(df[col] * poids_feuille[col] for col in colonnes_valides)
        denominateur = sum(poids_feuille[col] for col in colonnes_valides)
        # Même précaution que calculer_ipc() : pas d'arrondi à 2 décimales
        # ici, cette colonne alimente ensuite calculer_inflation_mom/yoy.
        df[nom_colonne] = (numerateur / denominateur).round(6)

        # Insérer dans Excel
        wb = load_workbook(nom_fichier)
        ws = wb[feuille]

        # Vérifier si la colonne existe déjà
        header_row = 1
        col_index = None
        for col in range(1, ws.max_column + 1):
            if ws.cell(row=header_row, column=col).value == nom_colonne:
                col_index = col
                break

        # Si pas trouvée → créer à la fin
        if col_index is None:
            col_index = ws.max_column + 1
            ws.cell(row=header_row, column=col_index, value=nom_colonne)

        # Construire dict {periode: valeur}
        ipc_dict = df[nom_colonne].to_dict()

        # Écrire dans la bonne colonne
        for row in range(2, ws.max_row + 1):
            cell_date = ws.cell(row=row, column=1).value
            if cell_date is None:
                continue
            try:
                periode = pd.to_datetime(cell_date).to_period("M")
            except Exception:
                continue
            if periode in ipc_dict:
                ws.cell(row=row, column=col_index, value=float(ipc_dict[periode]))

        wb.save(nom_fichier)
        wb.close()

        return df

    # --- Appliquer aux deux feuilles ---
    df_core = traiter_feuille(feuille_core, "IPC Core (%)")
    df_non_core = traiter_feuille(feuille_non_core, "IPC Non Core (%)")

    return df_core, df_non_core


def calculer_inflation_mom(nom_fichier: str, feuille: str, date_debut: str, date_fin: str):
    """
    Calcule l'inflation en glissement mensuel (mom) à partir des valeurs d'IPC d'une feuille
    et insère/réécrit les résultats dans une colonne fixe 'Inflation (%, mom)'.
    """

    # --- Charger la feuille en wide
    df = lire_feuille_wide(nom_fichier, feuille)

    # --- Assurer que la colonne 'date' est bien au format YYYY-MM
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.to_period("M")
        df.set_index("date", inplace=True)
    else:
        df.index = pd.to_datetime(df.index).to_period("M")

    # --- Transformer les arguments en période mensuelle
    date_debut = pd.Period(date_debut, freq="M")
    date_fin = pd.Period(date_fin, freq="M")

    # --- Filtrer la période
    df = df.loc[date_debut:date_fin]

    # --- Chercher la colonne IPC de référence
    for col in ["IPC (%)", "IPC Core (%)", "IPC Non Core (%)"]:
        if col in df.columns:
            col_ipc = col
            break
    else:
        raise ValueError("Aucune colonne IPC trouvée (IPC (%), IPC Core (%), ou IPC Non Core (%)).")

    # --- Calcul de l’inflation mom : (IPC_t / IPC_t-1 - 1) * 100
    df["Inflation (%, mom)"] = ((df[col_ipc] / df[col_ipc].shift(1) - 1) * 100).round(2)

    # --- Insérer dans Excel avec openpyxl
    wb = load_workbook(nom_fichier)
    ws = wb[feuille]

    # Trouver ou créer la colonne "Inflation (%, mom)"
    header_row = 1
    col_index_inflation = None
    for col in range(1, ws.max_column + 1):
        if ws.cell(row=header_row, column=col).value == "Inflation (%, mom)":
            col_index_inflation = col
            break

    if col_index_inflation is None:
        col_index_inflation = ws.max_column + 1
        ws.cell(row=header_row, column=col_index_inflation, value="Inflation (%, mom)")

    # Construire un dictionnaire {periode: valeur}
    infl_dict = df["Inflation (%, mom)"].to_dict()

    # Écrire les valeurs au bon endroit
    for row in range(2, ws.max_row + 1):
        cell_date = ws.cell(row=row, column=1).value  # date supposée en première colonne
        if cell_date is None:
            continue

        try:
            periode = pd.to_datetime(cell_date).to_period("M")
        except Exception:
            continue

        if periode in infl_dict and pd.notna(infl_dict[periode]):
            ws.cell(row=row, column=col_index_inflation, value=float(infl_dict[periode]))

    wb.save(nom_fichier)
    wb.close()

    return df


def calculer_inflation_yoy(nom_fichier: str, feuille: str, date_debut: str, date_fin: str):
    """
    Calcule l'inflation en glissement annuel (yoy) à partir des valeurs d'IPC d'une feuille
    et insère/réécrit les résultats dans une colonne fixe 'Inflation (%, yoy)'.
    """

    # --- Charger la feuille en wide
    df = lire_feuille_wide(nom_fichier, feuille)

    # --- Assurer que la colonne 'date' est bien au format YYYY-MM
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.to_period("M")
        df.set_index("date", inplace=True)
    else:
        df.index = pd.to_datetime(df.index).to_period("M")

    # --- Transformer les arguments en période mensuelle
    date_debut = pd.Period(date_debut, freq="M")
    date_fin = pd.Period(date_fin, freq="M")

    # --- Filtrer la période
    df = df.loc[date_debut:date_fin]

    # --- Chercher la colonne IPC de référence
    for col in ["IPC (%)", "IPC Core (%)", "IPC Non Core (%)"]:
        if col in df.columns:
            col_ipc = col
            break
    else:
        raise ValueError("Aucune colonne IPC trouvée (IPC (%), IPC Core (%), ou IPC Non Core (%)).")

    # --- Calcul de l’inflation yoy : (IPC_t / IPC_t-12 - 1) * 100
    df["Inflation (%, yoy)"] = ((df[col_ipc] / df[col_ipc].shift(12) - 1) * 100).round(2)

    # --- Insérer dans Excel avec openpyxl
    wb = load_workbook(nom_fichier)
    ws = wb[feuille]

    # Trouver ou créer la colonne "Inflation (%, yoy)"
    header_row = 1
    col_index_inflation = None
    for col in range(1, ws.max_column + 1):
        if ws.cell(row=header_row, column=col).value == "Inflation (%, yoy)":
            col_index_inflation = col
            break

    if col_index_inflation is None:
        col_index_inflation = ws.max_column + 1
        ws.cell(row=header_row, column=col_index_inflation, value="Inflation (%, yoy)")

    # Construire un dictionnaire {periode: valeur}
    infl_dict = df["Inflation (%, yoy)"].to_dict()

    # Écrire les valeurs au bon endroit
    for row in range(2, ws.max_row + 1):
        cell_date = ws.cell(row=row, column=1).value  # date supposée en première colonne
        if cell_date is None:
            continue

        try:
            periode = pd.to_datetime(cell_date).to_period("M")
        except Exception:
            continue

        if periode in infl_dict and pd.notna(infl_dict[periode]):
            ws.cell(row=row, column=col_index_inflation, value=float(infl_dict[periode]))

    wb.save(nom_fichier)
    wb.close()

    return df


def calculer_inflation_elements_mom(nom_fichier: str, feuille: str, date_debut: str, date_fin: str):
    """
    Calcule l'inflation mensuelle (MoM, %) uniquement pour les colonnes
    définies dans categories.json + weights.json, et insère les résultats
    dans la feuille Excel (Inflation_<élément>_MoM (%)).
    """

    # --- Charger la feuille wide
    df = lire_feuille_wide(nom_fichier, feuille)

    # --- Normaliser date -> Period M
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M")
        df.set_index("date", inplace=True)
    else:
        df.index = pd.to_datetime(df.index, errors="coerce").to_period("M")

    # --- Périodes demandées
    d_debut = pd.Period(date_debut, freq="M")
    d_fin = pd.Period(date_fin, freq="M")
    df = df.loc[d_debut:d_fin].copy()

    # --- Charger poids et catégories
    from config.settings import BASE_DIR

    CONFIG_PATH = BASE_DIR / "config" / "weights.json"
    CATEG_PATH = BASE_DIR / "config" / "categories.json"

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        all_weights = json.load(f)
    with open(CATEG_PATH, "r", encoding="utf-8") as f:
        categories = json.load(f)

    poids_feuille = extraire_poids(all_weights.get(feuille, {}))
    if not poids_feuille:
        raise ValueError(f"Aucun poids trouvé pour la feuille '{feuille}' dans weights.json")

    # --- Normalisation des noms pour comparer
    poids_set = {k.strip().lower() for k in poids_feuille.keys()}
    categ_set = {c.strip().lower() for c in extraire_toutes_categories(categories)}

    # Colonnes valides = intersection
    colonnes_valides = [
        col for col in df.columns if col.strip().lower() in poids_set and col.strip().lower() in categ_set
    ]

    if not colonnes_valides:
        raise ValueError(
            f"Aucune colonne valide trouvée.\n"
            f"Colonnes Excel = {sorted(df.columns.tolist())}\n"
            f"Colonnes weights.json = {sorted(poids_feuille.keys())}\n"
            f"Colonnes categories.json = {sorted(list(categ_set))}"
        )

    # --- Calcul inflation MoM uniquement pour colonnes valides
    df_infl = pd.DataFrame(index=df.index)
    for col in colonnes_valides:
        prev1 = df[col].shift(1)  # <-- MoM = (t - t-1) / t-1
        infl = ((df[col] - prev1) / prev1) * 100
        df_infl[f"Inflation_MoM (%)_{col}"] = infl.replace([np.inf, -np.inf], np.nan).round(2)

    # --- Écriture dans Excel
    wb = load_workbook(nom_fichier)
    ws = wb[feuille]

    # Dictionnaire colonnes existantes
    header_row = 1
    col_map = {ws.cell(row=header_row, column=c).value: c for c in range(1, ws.max_column + 1)}

    for col_name in df_infl.columns:
        # Trouver ou créer la colonne
        if col_name in col_map:
            col_index = col_map[col_name]
        else:
            col_index = ws.max_column + 1
            ws.cell(row=header_row, column=col_index, value=col_name)
            col_map[col_name] = col_index

        # Écrire les valeurs
        infl_dict = df_infl[col_name].to_dict()
        for r in range(2, ws.max_row + 1):
            cell_date = ws.cell(row=r, column=1).value
            if cell_date is None:
                continue
            try:
                periode = pd.to_datetime(cell_date, errors="coerce").to_period("M")
            except Exception:
                continue
            if periode in infl_dict:
                val = infl_dict[periode]
                if pd.notna(val):
                    ws.cell(row=r, column=col_index, value=float(val))

    wb.save(nom_fichier)
    wb.close()

    return df_infl


def calculer_inflation_elements_yoy(nom_fichier: str, feuille: str, date_debut: str, date_fin: str):
    """
    Calcule l'inflation annuelle (YoY, %) uniquement pour les colonnes
    définies dans categories.json + weights.json, et insère les résultats
    dans la feuille Excel (Inflation_<élément> (%)).
    """

    # --- Charger la feuille wide
    df = lire_feuille_wide(nom_fichier, feuille)

    # --- Normaliser date -> Period M
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M")
        df.set_index("date", inplace=True)
    else:
        df.index = pd.to_datetime(df.index, errors="coerce").to_period("M")

    # --- Périodes demandées
    d_debut = pd.Period(date_debut, freq="M")
    d_fin = pd.Period(date_fin, freq="M")
    df = df.loc[d_debut:d_fin].copy()

    # --- Charger poids et catégories
    from config.settings import BASE_DIR

    CONFIG_PATH = BASE_DIR / "config" / "weights.json"
    CATEG_PATH = BASE_DIR / "config" / "categories.json"

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        all_weights = json.load(f)
    with open(CATEG_PATH, "r", encoding="utf-8") as f:
        categories = json.load(f)

    poids_feuille = extraire_poids(all_weights.get(feuille, {}))
    if not poids_feuille:
        raise ValueError(f"Aucun poids trouvé pour la feuille '{feuille}' dans weights.json")

    # --- Normalisation des noms pour comparer
    poids_set = {k.strip().lower() for k in poids_feuille.keys()}
    categ_set = {c.strip().lower() for c in extraire_toutes_categories(categories)}

    # Colonnes valides = intersection
    colonnes_valides = [
        col for col in df.columns if col.strip().lower() in poids_set and col.strip().lower() in categ_set
    ]

    if not colonnes_valides:
        raise ValueError(
            f"Aucune colonne valide trouvée.\n"
            f"Colonnes Excel = {sorted(df.columns.tolist())}\n"
            f"Colonnes weights.json = {sorted(poids_feuille.keys())}\n"
            f"Colonnes categories.json = {sorted(list(categ_set))}"
        )

    # --- Calcul inflation YoY uniquement pour colonnes valides
    df_infl = pd.DataFrame(index=df.index)
    for col in colonnes_valides:
        prev12 = df[col].shift(12)
        infl = ((df[col] - prev12) / prev12) * 100
        df_infl[f"Inflation_YoY (%)_{col}"] = infl.replace([np.inf, -np.inf], np.nan).round(2)

    # --- Écriture dans Excel
    wb = load_workbook(nom_fichier)
    ws = wb[feuille]

    # Dictionnaire colonnes existantes
    header_row = 1
    col_map = {ws.cell(row=header_row, column=c).value: c for c in range(1, ws.max_column + 1)}

    for col_name in df_infl.columns:
        # Trouver ou créer la colonne
        if col_name in col_map:
            col_index = col_map[col_name]
        else:
            col_index = ws.max_column + 1
            ws.cell(row=header_row, column=col_index, value=col_name)
            col_map[col_name] = col_index

        # Écrire les valeurs
        infl_dict = df_infl[col_name].to_dict()
        for r in range(2, ws.max_row + 1):
            cell_date = ws.cell(row=r, column=1).value
            if cell_date is None:
                continue
            try:
                periode = pd.to_datetime(cell_date, errors="coerce").to_period("M")
            except Exception:
                continue
            if periode in infl_dict:
                val = infl_dict[periode]
                if pd.notna(val):
                    ws.cell(row=r, column=col_index, value=float(val))

    wb.save(nom_fichier)
    wb.close()

    return df_infl


def calculer_contributions_pp_mom(nom_fichier: str, feuille: str, date_debut: str, date_fin: str):
    """
    Calcule les contributions mensuelles (MoM, en pp) pour CHAQUE élément du panier
    (selon categories.json) et écrit une colonne par élément dans Excel.

    Retourne :
      df_contrib : DataFrame avec toutes les colonnes Contrib_<élément>_MoM
      ipc_info   : DataFrame avec IPC_level et IPC_mom
    """
    # --- Charger la feuille wide
    df = lire_feuille_wide(nom_fichier, feuille)

    # --- Normaliser date -> Period M
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M")
        df.set_index("date", inplace=True)
    else:
        df.index = pd.to_datetime(df.index, errors="coerce").to_period("M")

    # --- Périodes demandées
    d_debut = pd.Period(date_debut, freq="M")
    d_fin = pd.Period(date_fin, freq="M")
    df = df.loc[d_debut:d_fin].copy()

    # --- Charger poids et catégories
    from config.settings import BASE_DIR

    CONFIG_PATH = BASE_DIR / "config" / "weights.json"
    CATEG_PATH = BASE_DIR / "config" / "categories.json"

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        all_weights = json.load(f)
    with open(CATEG_PATH, "r", encoding="utf-8") as f:
        categories = json.load(f)

    poids_feuille = extraire_poids(all_weights.get(feuille, {}))
    if not poids_feuille:
        raise ValueError(f"Aucun poids trouvé pour la feuille '{feuille}' dans weights.json")

    colonnes_valides = [col for col in df.columns if col in poids_feuille]
    if not colonnes_valides:
        raise ValueError("Aucune colonne du fichier Excel ne correspond aux poids du panier.")

    # --- IPC global — pondération recalculée MOIS PAR MOIS sur les seules
    # colonnes disponibles ce mois-là (poids_serie.dot(valeurs.notna())),
    # plutôt qu'un total fixe : un panier à sous-produits partiellement
    # renseignés (ex. Produits_agricoles_frais, 4 des 8 sans source récente)
    # produisait sinon un IPC_level NaN dès qu'UNE colonne manquait, ce qui
    # annulait la contribution de TOUS les éléments ce mois-là, pas
    # seulement celle de l'élément manquant.
    poids_serie = pd.Series({c: float(poids_feuille[c]) for c in colonnes_valides})
    valeurs = df[colonnes_valides].astype(float)
    denom_ligne = valeurs.notna().astype(float).dot(poids_serie)
    numer = valeurs.fillna(0.0).dot(poids_serie)
    ipc_level = (numer / denom_ligne).rename("IPC_level")
    ipc_info = ipc_level.to_frame()
    ipc_info["IPC_prev1"] = ipc_info["IPC_level"].shift(1)
    ipc_info["IPC_mom_pct"] = ((ipc_info["IPC_level"] - ipc_info["IPC_prev1"]) / ipc_info["IPC_prev1"]) * 100

    # --- Calcul contributions détaillées (MoM)
    df_contrib = pd.DataFrame(index=df.index)
    for col in colonnes_valides:
        poids_i = float(poids_feuille[col])
        delta = df[col] - df[col].shift(1)  # <-- MoM
        contrib = (delta / ipc_info["IPC_prev1"]) * (poids_i / denom_ligne) * 100
        df_contrib[f"Contrib_MoM_{col} (pp)"] = contrib.replace([np.inf, -np.inf], np.nan).fillna(0.0).round(3)

    # --- Écriture Excel (une colonne par élément, ordre de categories.json)
    wb = load_workbook(nom_fichier)
    ws = wb[feuille]

    header_row = 1
    col_map = {ws.cell(row=header_row, column=c).value: c for c in range(1, ws.max_column + 1)}

    # Parcours hiérarchique des catégories pour garder l’ordre
    for _cat, elements in categories.items():
        for elem in elements:
            col_name = f"Contrib_MoM_{elem} (pp)"
            if col_name in df_contrib.columns:
                # Trouver ou créer la colonne
                if col_name in col_map:
                    col_index = col_map[col_name]
                else:
                    col_index = ws.max_column + 1
                    ws.cell(row=header_row, column=col_index, value=col_name)
                    col_map[col_name] = col_index

                contrib_dict = df_contrib[col_name].to_dict()

                for r in range(2, ws.max_row + 1):
                    cell_date = ws.cell(row=r, column=1).value
                    if cell_date is None:
                        continue
                    try:
                        periode = pd.to_datetime(cell_date, errors="coerce").to_period("M")
                    except Exception:
                        continue
                    if periode in contrib_dict:
                        ws.cell(row=r, column=col_index, value=float(contrib_dict[periode]))

    wb.save(nom_fichier)
    wb.close()

    return df_contrib, ipc_info


def calculer_contributions_pp_yoy(nom_fichier: str, feuille: str, date_debut: str, date_fin: str):
    """
    Calcule les contributions en pp pour CHAQUE élément du panier
    (selon categories.json) et écrit une colonne par élément dans Excel.

    Retourne :
      df_contrib : DataFrame avec toutes les colonnes Contrib_<élément>
      ipc_info   : DataFrame avec IPC_level et IPC_yoy
    """
    # --- Charger la feuille wide
    df = lire_feuille_wide(nom_fichier, feuille)

    # --- Normaliser date -> Period M
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M")
        df.set_index("date", inplace=True)
    else:
        df.index = pd.to_datetime(df.index, errors="coerce").to_period("M")

    # --- Périodes demandées
    d_debut = pd.Period(date_debut, freq="M")
    d_fin = pd.Period(date_fin, freq="M")
    df = df.loc[d_debut:d_fin].copy()

    # --- Charger poids et catégories
    from config.settings import BASE_DIR

    CONFIG_PATH = BASE_DIR / "config" / "weights.json"
    CATEG_PATH = BASE_DIR / "config" / "categories.json"

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        all_weights = json.load(f)
    with open(CATEG_PATH, "r", encoding="utf-8") as f:
        categories = json.load(f)

    poids_feuille = extraire_poids(all_weights.get(feuille, {}))
    if not poids_feuille:
        raise ValueError(f"Aucun poids trouvé pour la feuille '{feuille}' dans weights.json")

    colonnes_valides = [col for col in df.columns if col in poids_feuille]
    if not colonnes_valides:
        raise ValueError("Aucune colonne du fichier Excel ne correspond aux poids du panier.")

    # --- IPC global — pondération recalculée mois par mois sur les seules
    # colonnes disponibles (voir le commentaire équivalent dans
    # calculer_contributions_pp_mom).
    poids_serie = pd.Series({c: float(poids_feuille[c]) for c in colonnes_valides})
    valeurs = df[colonnes_valides].astype(float)
    denom_ligne = valeurs.notna().astype(float).dot(poids_serie)
    numer = valeurs.fillna(0.0).dot(poids_serie)
    ipc_level = (numer / denom_ligne).rename("IPC_level")
    ipc_info = ipc_level.to_frame()
    ipc_info["IPC_prev12"] = ipc_info["IPC_level"].shift(12)
    ipc_info["IPC_yoy_pct"] = ((ipc_info["IPC_level"] - ipc_info["IPC_prev12"]) / ipc_info["IPC_prev12"]) * 100

    # --- Calcul contributions détaillées
    df_contrib = pd.DataFrame(index=df.index)
    for col in colonnes_valides:
        poids_i = float(poids_feuille[col])
        delta = df[col] - df[col].shift(12)
        contrib = (delta / ipc_info["IPC_prev12"]) * (poids_i / denom_ligne) * 100
        df_contrib[f"Contrib_YoY_{col} (pp)"] = contrib.replace([np.inf, -np.inf], np.nan).fillna(0.0).round(3)

    # --- Écriture Excel (une colonne par élément, ordre de categories.json)
    wb = load_workbook(nom_fichier)
    ws = wb[feuille]

    header_row = 1
    col_map = {ws.cell(row=header_row, column=c).value: c for c in range(1, ws.max_column + 1)}

    # Parcours hiérarchique des catégories pour garder l’ordre
    for _cat, elements in categories.items():
        for elem in elements:
            col_name = f"Contrib_YoY_{elem} (pp)"
            if col_name in df_contrib.columns:
                # Trouver ou créer la colonne
                if col_name in col_map:
                    col_index = col_map[col_name]
                else:
                    col_index = ws.max_column + 1
                    ws.cell(row=header_row, column=col_index, value=col_name)
                    col_map[col_name] = col_index

                contrib_dict = df_contrib[col_name].to_dict()

                for r in range(2, ws.max_row + 1):
                    cell_date = ws.cell(row=r, column=1).value
                    if cell_date is None:
                        continue
                    try:
                        periode = pd.to_datetime(cell_date, errors="coerce").to_period("M")
                    except Exception:
                        continue
                    if periode in contrib_dict:
                        ws.cell(row=r, column=col_index, value=float(contrib_dict[periode]))

    wb.save(nom_fichier)
    wb.close()

    return df_contrib, ipc_info


def calculer_contributions_core_noncore_mom(
    nom_fichier: str, feuille_core: str, feuille_noncore: str, feuille_categories: str, date_debut: str, date_fin: str
):
    """
    Calcule la contribution mensuelle (MoM, en pp) du Core et du Non-Core
    dans l'inflation globale (feuille 'categories').
    Insère les colonnes 'Contrib_Core_MoM (pp)' et 'Contrib_Non_Core_MoM (pp)' dans la feuille categories.

    Retourne :
        df_contrib : DataFrame avec Contrib_Core_MoM et Contrib_Non_Core_MoM
        ipc_info   : DataFrame avec IPC_level et IPC_mom_pct
    """

    # --- 1. Charger les 3 feuilles
    df_core = lire_feuille_wide(nom_fichier, feuille_core)
    df_noncore = lire_feuille_wide(nom_fichier, feuille_noncore)
    df_cat = lire_feuille_wide(nom_fichier, feuille_categories)

    # --- 2. Normaliser les dates
    for df in (df_core, df_noncore, df_cat):
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M")
            df.set_index("date", inplace=True)
        else:
            df.index = pd.to_datetime(df.index, errors="coerce").to_period("M")

    # --- 3. Restreindre à la période demandée
    d_debut = pd.Period(date_debut, freq="M")
    d_fin = pd.Period(date_fin, freq="M")
    df_core = df_core.loc[d_debut:d_fin].copy()
    df_noncore = df_noncore.loc[d_debut:d_fin].copy()
    df_cat = df_cat.loc[d_debut:d_fin].copy()

    # --- 4. Charger les poids
    from config.settings import BASE_DIR

    CONFIG_PATH = BASE_DIR / "config" / "weights.json"
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        all_weights = json.load(f)

    poids_core = extraire_poids(all_weights.get(feuille_core, {}))
    poids_noncore = extraire_poids(all_weights.get(feuille_noncore, {}))
    poids_cat = extraire_poids(all_weights.get(feuille_categories, {}))

    # --- 5. Colonnes valides
    colonnes_core = [c for c in df_core.columns if c in poids_core]
    colonnes_noncore = [c for c in df_noncore.columns if c in poids_noncore]
    colonnes_cat = [c for c in df_cat.columns if c in poids_cat]

    if not colonnes_core or not colonnes_noncore or not colonnes_cat:
        raise ValueError("Colonnes manquantes ou incohérence entre Excel et weights.json")

    # --- 6. IPC global
    numer_cat = sum(df_cat[col] * poids_cat[col] for col in colonnes_cat)
    denom_cat = sum(poids_cat[col] for col in colonnes_cat)
    ipc_level = (numer_cat / denom_cat).rename("IPC_level")
    ipc_prev1 = ipc_level.shift(1)

    # --- 7. IPC Core et Non-Core
    numer_core = sum(df_core[col] * poids_core[col] for col in colonnes_core)
    denom_core = sum(poids_core[col] for col in colonnes_core)
    ipc_core = numer_core / denom_core

    numer_noncore = sum(df_noncore[col] * poids_noncore[col] for col in colonnes_noncore)
    denom_noncore = sum(poids_noncore[col] for col in colonnes_noncore)
    ipc_noncore = numer_noncore / denom_noncore

    # Certains mois n'ont que des composantes partielles (ex. sous-produits
    # sans source pour Produits_agricoles_frais) : la somme pondérée y est
    # NaN alors que la colonne 'IPC Non Core (%)' porte déjà la bonne
    # valeur (calculée ou intégrée par ailleurs). On ne comble que ce trou.
    if "IPC Non Core (%)" in df_noncore.columns:
        ipc_noncore = ipc_noncore.fillna(df_noncore["IPC Non Core (%)"])
    if "IPC Core (%)" in df_core.columns:
        ipc_core = ipc_core.fillna(df_core["IPC Core (%)"])

    # --- 8. Contributions MoM (pp)
    contrib_core = ((ipc_core - ipc_core.shift(1)) / ipc_prev1) * (denom_core / denom_cat) * 100
    contrib_noncore = ((ipc_noncore - ipc_noncore.shift(1)) / ipc_prev1) * (denom_noncore / denom_cat) * 100

    df_contrib = pd.DataFrame(
        {
            "Contrib_Core_MoM (pp)": contrib_core.replace([np.inf, -np.inf], np.nan).fillna(0.0).round(3),
            "Contrib_Non_Core_MoM (pp)": contrib_noncore.replace([np.inf, -np.inf], np.nan).fillna(0.0).round(3),
        }
    )

    # --- 9. IPC global MoM %
    ipc_mom_pct = ((ipc_level - ipc_prev1) / ipc_prev1) * 100
    ipc_info = pd.DataFrame({"IPC_level": ipc_level, "IPC_mom_pct": ipc_mom_pct})

    # --- 10. Écriture dans Excel
    wb = load_workbook(nom_fichier)
    ws = wb[feuille_categories]
    header_row = 1
    col_map = {ws.cell(row=header_row, column=c).value: c for c in range(1, ws.max_column + 1)}

    for col_name in df_contrib.columns:
        if col_name in col_map:
            col_index = col_map[col_name]
        else:
            col_index = ws.max_column + 1
            ws.cell(row=header_row, column=col_index, value=col_name)
            col_map[col_name] = col_index

        contrib_dict = df_contrib[col_name].to_dict()
        for r in range(2, ws.max_row + 1):
            cell_date = ws.cell(row=r, column=1).value
            if cell_date is None:
                continue
            try:
                periode = pd.to_datetime(cell_date, errors="coerce").to_period("M")
            except Exception:
                continue
            if periode in contrib_dict:
                ws.cell(row=r, column=col_index, value=float(contrib_dict[periode]))

    wb.save(nom_fichier)
    wb.close()

    return df_contrib, ipc_info


def calculer_contributions_core_noncore_yoy(
    nom_fichier: str, feuille_core: str, feuille_noncore: str, feuille_categories: str, date_debut: str, date_fin: str
):
    """
    Calcule la contribution en points de pourcentage (pp) du Core et du Non-Core
    dans l'inflation globale (feuille 'categories').
    Insère les colonnes 'Contrib_Core (pp)' et 'Contrib_Non_Core (pp)' dans la feuille categories.
    Retourne :
        df_contrib : DataFrame avec Contrib_Core et Contrib_Non_Core
        ipc_info   : DataFrame avec IPC_level et IPC_yoy_pct
    """

    # --- 1. Charger les 3 feuilles
    df_core = lire_feuille_wide(nom_fichier, feuille_core)
    df_noncore = lire_feuille_wide(nom_fichier, feuille_noncore)
    df_cat = lire_feuille_wide(nom_fichier, feuille_categories)

    # --- 2. Normaliser les dates
    for df in (df_core, df_noncore, df_cat):
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M")
            df.set_index("date", inplace=True)
        else:
            df.index = pd.to_datetime(df.index, errors="coerce").to_period("M")

    # --- 3. Restreindre à la période demandée
    d_debut = pd.Period(date_debut, freq="M")
    d_fin = pd.Period(date_fin, freq="M")
    df_core = df_core.loc[d_debut:d_fin].copy()
    df_noncore = df_noncore.loc[d_debut:d_fin].copy()
    df_cat = df_cat.loc[d_debut:d_fin].copy()

    # --- 4. Charger les poids
    from config.settings import BASE_DIR

    CONFIG_PATH = BASE_DIR / "config" / "weights.json"
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        all_weights = json.load(f)

    poids_core = extraire_poids(all_weights.get(feuille_core, {}))
    poids_noncore = extraire_poids(all_weights.get(feuille_noncore, {}))
    poids_cat = extraire_poids(all_weights.get(feuille_categories, {}))

    # --- 5. Colonnes valides
    colonnes_core = [c for c in df_core.columns if c in poids_core]
    colonnes_noncore = [c for c in df_noncore.columns if c in poids_noncore]
    colonnes_cat = [c for c in df_cat.columns if c in poids_cat]

    if not colonnes_core or not colonnes_noncore or not colonnes_cat:
        raise ValueError("Colonnes manquantes ou incohérence entre Excel et weights.json")

    # --- 6. IPC global
    numer_cat = sum(df_cat[col] * poids_cat[col] for col in colonnes_cat)
    denom_cat = sum(poids_cat[col] for col in colonnes_cat)
    ipc_level = (numer_cat / denom_cat).rename("IPC_level")
    ipc_prev12 = ipc_level.shift(12)

    # --- 7. IPC Core et Non-Core
    numer_core = sum(df_core[col] * poids_core[col] for col in colonnes_core)
    denom_core = sum(poids_core[col] for col in colonnes_core)
    ipc_core = numer_core / denom_core

    numer_noncore = sum(df_noncore[col] * poids_noncore[col] for col in colonnes_noncore)
    denom_noncore = sum(poids_noncore[col] for col in colonnes_noncore)
    ipc_noncore = numer_noncore / denom_noncore

    # Certains mois n'ont que des composantes partielles (ex. sous-produits
    # sans source pour Produits_agricoles_frais) : la somme pondérée y est
    # NaN alors que la colonne 'IPC Non Core (%)' porte déjà la bonne
    # valeur (calculée ou intégrée par ailleurs). On ne comble que ce trou.
    if "IPC Non Core (%)" in df_noncore.columns:
        ipc_noncore = ipc_noncore.fillna(df_noncore["IPC Non Core (%)"])
    if "IPC Core (%)" in df_core.columns:
        ipc_core = ipc_core.fillna(df_core["IPC Core (%)"])

    # --- 8. Contribution Core et Non-Core
    contrib_core = ((ipc_core - ipc_core.shift(12)) / ipc_prev12) * (denom_core / denom_cat) * 100
    contrib_noncore = ((ipc_noncore - ipc_noncore.shift(12)) / ipc_prev12) * (denom_noncore / denom_cat) * 100

    df_contrib = pd.DataFrame(
        {
            "Contrib_Core_YoY (pp)": contrib_core.replace([np.inf, -np.inf], np.nan).fillna(0.0).round(3),
            "Contrib_Non_Core_YoY (pp)": contrib_noncore.replace([np.inf, -np.inf], np.nan).fillna(0.0).round(3),
        }
    )

    # --- 9. IPC global yoy
    ipc_yoy_pct = ((ipc_level - ipc_prev12) / ipc_prev12) * 100
    ipc_info = pd.DataFrame({"IPC_level": ipc_level, "IPC_yoy_pct": ipc_yoy_pct})

    # --- 10. Écriture Excel
    wb = load_workbook(nom_fichier)
    ws = wb[feuille_categories]
    header_row = 1
    col_map = {ws.cell(row=header_row, column=c).value: c for c in range(1, ws.max_column + 1)}

    for col_name in df_contrib.columns:
        if col_name in col_map:
            col_index = col_map[col_name]
        else:
            col_index = ws.max_column + 1
            ws.cell(row=header_row, column=col_index, value=col_name)
            col_map[col_name] = col_index

        contrib_dict = df_contrib[col_name].to_dict()
        for r in range(2, ws.max_row + 1):
            cell_date = ws.cell(row=r, column=1).value
            if cell_date is None:
                continue
            try:
                periode = pd.to_datetime(cell_date, errors="coerce").to_period("M")
            except Exception:
                continue
            if periode in contrib_dict:
                ws.cell(row=r, column=col_index, value=float(contrib_dict[periode]))

    wb.save(nom_fichier)
    wb.close()

    return df_contrib, ipc_info


def pipeline_core_noncore(
    nom_fichier: str, feuille_core: str, feuille_non_core: str, feuille_categories: str, date_debut: str, date_fin: str
):
    """
    Exécute la chaîne complète Core / Non-Core en travaillant sur une copie
    du fichier source ("*_et_calculs.xlsx").
    Étapes :
      1) IPC Core / Non-Core
      2) Inflation MoM Core / Non-Core
      3) Inflation YoY Core / Non-Core
      4) Contributions MoM Core / Non-Core
      5) Contributions YoY Core / Non-Core
    """

    # --- 0. Fichier de travail (data/processed/) ---
    fichier_calculs = fichier_de_travail(nom_fichier)

    # --- 1. IPC Core / Non-Core ---
    df_ipc_core_noncore = calculer_ipc_core_noncore(
        fichier_calculs, feuille_core, feuille_non_core, date_debut, date_fin
    )

    # --- 2. Inflation MoM Core / Non-Core ---
    df_infl_core_mom = calculer_inflation_mom(fichier_calculs, feuille_core, date_debut, date_fin)
    df_infl_noncore_mom = calculer_inflation_mom(fichier_calculs, feuille_non_core, date_debut, date_fin)

    # --- 3. Inflation YoY Core / Non-Core ---
    df_infl_core_yoy = calculer_inflation_yoy(fichier_calculs, feuille_core, date_debut, date_fin)
    df_infl_noncore_yoy = calculer_inflation_yoy(fichier_calculs, feuille_non_core, date_debut, date_fin)

    # --- 4. Contributions MoM Core / Non-Core ---
    df_contrib_core_noncore_mom, ipc_info_mom = calculer_contributions_core_noncore_mom(
        fichier_calculs, feuille_core, feuille_non_core, feuille_categories, date_debut, date_fin
    )

    # --- 5. Contributions YoY Core / Non-Core ---
    df_contrib_core_noncore_yoy, ipc_info_yoy = calculer_contributions_core_noncore_yoy(
        fichier_calculs, feuille_core, feuille_non_core, feuille_categories, date_debut, date_fin
    )

    return {
        "ipc": df_ipc_core_noncore,
        "infl_core_mom": df_infl_core_mom,
        "infl_noncore_mom": df_infl_noncore_mom,
        "infl_core_yoy": df_infl_core_yoy,
        "infl_noncore_yoy": df_infl_noncore_yoy,
        "contrib_mom": df_contrib_core_noncore_mom,
        "ipc_mom": ipc_info_mom,
        "contrib_yoy": df_contrib_core_noncore_yoy,
        "ipc_yoy": ipc_info_yoy,
    }


def pipeline_calculs(nom_fichier: str, feuille: str, date_debut: str, date_fin: str):
    """
    Exécute la chaîne complète des calculs IPC et inflation
    en travaillant sur une copie unique ("fichier_de_donnes_et_calculs.xlsx").
    """

    # --- 0. Fichier de travail (data/processed/)
    fichier_calculs = fichier_de_travail(nom_fichier)

    # --- 1. IPC
    df_ipc = calculer_ipc(fichier_calculs, feuille, date_debut, date_fin)

    # --- 2. Inflation éléments MoM
    df_infl_elem_mom = calculer_inflation_elements_mom(fichier_calculs, feuille, date_debut, date_fin)

    # --- 3. Inflation globale MoM
    df_infl_mom = calculer_inflation_mom(fichier_calculs, feuille, date_debut, date_fin)

    # --- 4. Inflation éléments YoY
    df_infl_elem_yoy = calculer_inflation_elements_yoy(fichier_calculs, feuille, date_debut, date_fin)

    # --- 5. Inflation globale YoY
    df_infl_yoy = calculer_inflation_yoy(fichier_calculs, feuille, date_debut, date_fin)

    # --- 6. Contributions MoM
    df_contrib_mom, ipc_info_mom = calculer_contributions_pp_mom(fichier_calculs, feuille, date_debut, date_fin)

    # --- 7. Contributions YoY
    df_contrib_yoy, ipc_info_yoy = calculer_contributions_pp_yoy(fichier_calculs, feuille, date_debut, date_fin)

    return {
        "ipc": df_ipc,
        "infl_elem_mom": df_infl_elem_mom,
        "infl_mom": df_infl_mom,
        "infl_elem_yoy": df_infl_elem_yoy,
        "infl_yoy": df_infl_yoy,
        "contrib_mom": df_contrib_mom,
        "ipc_mom": ipc_info_mom,
        "contrib_yoy": df_contrib_yoy,
        "ipc_yoy": ipc_info_yoy,
    }


def get_max_date(nom_fichier: str, feuille: str) -> pd.Timestamp:
    """
    Récupère la date maximale (plus récente) dans l'index d'une feuille Excel.
    """
    df = pd.read_excel(nom_fichier, sheet_name=feuille, index_col=0, parse_dates=True)
    return df.index.max()


def pipeline_global(Fichier_de_donnees: str):
    """
    Fonction globale qui exécute les différents pipelines de calculs
    (Grand Alger, Categories, National, Core/Non-Core).

    Paramètres
    ----------
    Fichier_de_donnees : str
        Chemin vers le fichier Excel contenant toutes les feuilles.
    """

    # --- 0) Fichier de travail : c'est lui qui porte toutes les feuilles
    # (la feuille 'core' n'existe pas dans le fichier brut).
    fichier_travail = fichier_de_travail(Fichier_de_donnees)
    creer_feuille_core_si_absente(fichier_travail)

    # --- 1) Dates de référence
    date_debut = "2002-01"  # fixe
    # On va chercher la date max dans chaque feuille
    date_fin_grand_alger = get_max_date(fichier_travail, "Grand_Alger")
    date_fin_categories = get_max_date(fichier_travail, "categories")
    date_fin_national = get_max_date(fichier_travail, "national")
    date_fin_core = get_max_date(fichier_travail, "core")
    date_fin_non_core = get_max_date(fichier_travail, "Produits_agricoles_frais")

    # La date de fin globale = la plus récente parmi toutes
    date_fin_globale = max(
        date_fin_grand_alger, date_fin_categories, date_fin_national, date_fin_core, date_fin_non_core
    )

    # --- 2) Pipelines individuels
    print("➡️ Pipeline Grand Alger")
    pipeline_calculs(Fichier_de_donnees, "Grand_Alger", date_debut, date_fin_grand_alger.strftime("%Y-%m"))

    print("➡️ Pipeline Categories")
    pipeline_calculs(Fichier_de_donnees, "categories", date_debut, date_fin_categories.strftime("%Y-%m"))

    print("➡️ Pipeline National")
    pipeline_calculs(Fichier_de_donnees, "national", date_debut, date_fin_national.strftime("%Y-%m"))

    # --- 2bis) National : IPC officiel tel quel (voir ingerer_ipc_national_officiel)
    from config.settings import FICHIER_DONNEES_COMPLEMENTAIRES

    if os.path.exists(str(FICHIER_DONNEES_COMPLEMENTAIRES)):
        ingerer_ipc_national_officiel(Fichier_de_donnees, date_fin=date_fin_national.strftime("%Y-%m"))

    # --- 3) Pipeline Core vs Non-Core
    print("➡️ Pipeline Core / Non-Core")
    pipeline_core_noncore(
        nom_fichier=Fichier_de_donnees,
        feuille_core="core",
        feuille_non_core="Produits_agricoles_frais",
        feuille_categories="categories",
        date_debut=date_debut,
        date_fin=date_fin_globale.strftime("%Y-%m"),  # on prend la plus récente
    )

    # --- 4) Indices complémentaires nationaux (Réglementés / FCI / Core 2),
    # si le fichier complémentaire est présent.
    from config.settings import FICHIER_DONNEES_COMPLEMENTAIRES

    if os.path.exists(str(FICHIER_DONNEES_COMPLEMENTAIRES)):
        print("➡️ Pipeline Indices complémentaires nationaux (Réglementés / FCI / Core 2)")
        integrer_indices_complementaires_nationaux(Fichier_de_donnees)

    print("✅ Tous les pipelines ont été exécutés avec succès.")


def _lire_indices_complementaires_nationaux(fichier_complementaire: str) -> dict:
    """
    Lit la feuille 'FCI_REG' du fichier complémentaire (voir
    config.settings.FICHIER_DONNEES_COMPLEMENTAIRES) et répartit ses trois
    lignes vers les feuilles cibles national_reglementes / national_fci /
    national_core2.

    Ces trois indices (Réglementés, Fort Contenu d'Import, Hors Réglementés
    et Hors Agricoles frais = inflation sous-jacente 2) sont déjà calculés à
    la source, au niveau national : on les intègre tels quels, sans repasser
    par une pondération locale.

    Retour : {nom_feuille: {"poids": float, "libelle": str, "valeurs": {Timestamp: float}}}
    """
    from config.settings import (
        FEUILLE_NATIONAL_FCI,
        FEUILLE_NATIONAL_REGLEMENTES,
        FEUILLE_NATIONAL_CORE2,
    )

    wb = load_workbook(fichier_complementaire, read_only=True, data_only=True)
    ws = wb["FCI_REG"]
    lignes = list(ws.iter_rows(values_only=True))
    wb.close()

    entete = lignes[0]
    dates = [pd.Timestamp(d).replace(day=1) for d in entete[2:] if d is not None]

    resultats = {}
    for ligne in lignes[1:]:
        libelle = ligne[0]
        if not libelle:
            continue
        libelle_bas = str(libelle).lower()

        if "fort contenu d'import" in libelle_bas:
            feuille = FEUILLE_NATIONAL_FCI
        elif "hors" in libelle_bas and "agricoles" in libelle_bas:
            feuille = FEUILLE_NATIONAL_CORE2
        elif "réglementés" in libelle_bas:
            feuille = FEUILLE_NATIONAL_REGLEMENTES
        else:
            continue

        poids = ligne[1]
        valeurs = ligne[2:]
        resultats[feuille] = {
            "poids": poids,
            "libelle": str(libelle).strip(),
            "valeurs": {d: float(v) for d, v in zip(dates, valeurs) if v is not None},
        }

    return resultats


def integrer_indices_complementaires_nationaux(nom_fichier: str, fichier_complementaire: str = None):
    """
    Intègre dans le fichier de calculs les trois indices nationaux
    complémentaires (Réglementés, Fort Contenu d'Import, Core 2 = inflation
    sous-jacente 2) et calcule leur inflation MoM / YoY.

    N'a aucun effet si le fichier complémentaire est absent.
    """
    from config.settings import FICHIER_DONNEES_COMPLEMENTAIRES

    if fichier_complementaire is None:
        fichier_complementaire = str(FICHIER_DONNEES_COMPLEMENTAIRES)
    if not os.path.exists(fichier_complementaire):
        return None

    fichier_calculs = fichier_de_travail(nom_fichier)
    donnees = _lire_indices_complementaires_nationaux(fichier_complementaire)
    if not donnees:
        return None

    # --- Écrire (ou réécrire) chaque feuille : deux colonnes, 'date' et 'IPC (%)'.
    wb = load_workbook(fichier_calculs)
    for feuille, info in donnees.items():
        if feuille in wb.sheetnames:
            del wb[feuille]
        ws = wb.create_sheet(feuille)
        ws.cell(row=1, column=1, value="date")
        ws.cell(row=1, column=2, value="IPC (%)")
        for i, (date, valeur) in enumerate(sorted(info["valeurs"].items()), start=2):
            ws.cell(row=i, column=1, value=date.to_pydatetime())
            ws.cell(row=i, column=2, value=valeur)
    wb.save(fichier_calculs)
    wb.close()

    # --- Inflation MoM / YoY de chaque indice (réutilise les fonctions
    # génériques : elles cherchent la colonne 'IPC (%)').
    resultats = {}
    for feuille, info in donnees.items():
        dates_disponibles = sorted(info["valeurs"].keys())
        date_debut = dates_disponibles[0].strftime("%Y-%m")
        date_fin = dates_disponibles[-1].strftime("%Y-%m")
        calculer_inflation_mom(fichier_calculs, feuille, date_debut, date_fin)
        resultats[feuille] = calculer_inflation_yoy(fichier_calculs, feuille, date_debut, date_fin)

    return resultats


def _normaliser_libelle(texte) -> str:
    """Clé de comparaison robuste : sans accents, sans retour à la ligne,
    sans ponctuation, en minuscules. Sert à retrouver un libellé du fichier
    complémentaire malgré les sauts de ligne et variantes d'accentuation."""
    if texte is None:
        return ""
    texte = str(texte).replace("\n", " ")
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z]", "", texte).lower()


def _parser_bloc_large(fichier: str, feuille: str) -> dict:
    """
    Parse un onglet "large" du fichier complémentaire (une ligne par
    produit/groupe, une colonne 'Poids', puis une colonne par mois) et
    retourne {libellé normalisé: {"libelle": str, "poids": float,
    "valeurs": {Timestamp (jour=1): float}}}.

    Ces onglets répètent plusieurs fois les mêmes libellés (moyenne
    mensuelle, moyenne annuelle, taux d'inflation...) : seul le premier
    bloc (les valeurs mensuelles brutes) est conservé.
    """
    wb = load_workbook(fichier, read_only=True, data_only=True)
    ws = wb[feuille]
    lignes = list(ws.iter_rows(values_only=True))
    wb.close()

    entete = lignes[0]
    col_date = None
    for i, v in enumerate(entete):
        if hasattr(v, "year"):
            col_date = i
            break
    if col_date is None:
        raise ValueError(f"Aucune colonne de date trouvée dans '{feuille}'.")
    col_poids = col_date - 1
    dates = [pd.Timestamp(d).replace(day=1) for d in entete[col_date:] if d is not None]

    def est_code(v):
        return isinstance(v, str) and re.fullmatch(r"[A-Z0-9]+", v.strip()) is not None

    resultats = {}
    deja_vus = set()
    for ligne in lignes[1:]:
        libelle = None
        for i in range(col_poids - 1, -1, -1):
            if ligne[i] is not None and not est_code(ligne[i]):
                libelle = ligne[i]
                break
        if libelle is None:
            continue
        cle = _normaliser_libelle(libelle)
        if cle in deja_vus:
            break  # bloc suivant (répétition des mêmes libellés)
        deja_vus.add(cle)

        valeurs = {d: float(v) for d, v in zip(dates, ligne[col_date:]) if v is not None}
        resultats[cle] = {
            "libelle": str(libelle).strip(),
            "poids": ligne[col_poids],
            "valeurs": valeurs,
        }
    return resultats


# Correspondance colonne-projet -> libellé du fichier complémentaire.
# Les groupes (huit postes) sont identiques pour Alger et le national.
_GROUPES_PANIER = [
    ("Alimentations_Boissons_non_alcoolisées", "Alimentations - Boissons non alcoolisées"),
    ("Habillement_Chaussures", "Habillement - Chaussures"),
    ("Logements_Charges", "Logements - Charges"),
    ("Meubles_Articles_d_Ameublement", "Meubles et Articles d'Ameublement"),
    ("Santé_Hygiène_Corporelle", "Santé - Hygiène Corporelle"),
    ("Transports_Communications", "Transports et Communications"),
    ("Education_Culture_Loisirs", "Education - Culture - Loisirs"),
    ("Divers_NDA", "Divers (N.D.A)"),
]

_SOUS_ITEMS_ALIMENTATION = [
    ("Pain_Céréales", "Pain_Céréales"),
    ("Viandes_Abats_de_Mouton", "Viandes_Abats de Mouton"),
    ("Viandes_Abats_de_Bœufs", "Viandes_Abats de Bœufs"),
    ("Volailles_Lapins_Oeufs", "Volailles_Lapins_Oeufs"),
    ("Poissons_Frais", "Poissons Frais"),
    ("Viandes_Poissons_en_Conserves", "Vaindes_Poissons en Conserves"),
    ("Légumes", "Légumes"),
    ("Fruits", "Fruits"),
    ("Pommes_de_Terre", "Pommes de Terre"),
    ("Laits_Fromages_Dérivés", "Laits_Fromages Dérivés"),
    ("Huiles_Graisses", "Huiles Graisses"),
    ("Sucres_Produits_Sucrés", "Sucres_Produits Sucrés"),
    ("Cafés_Thé_Infusion", "Cafés_Thé_Infusion"),
    ("Boissons_non_Alcoolisées", "Boissons non Alcoolisées"),
    ("Autres_Produits_Alimentaires", "Autres Produits Alimentaires"),
]

# Quatre des huit postes du panier "Produits agricoles frais" du projet
# (Viandes_de_poulet, Œufs, Légumes_frais, Fruits_frais) n'existent pas à ce
# niveau de détail dans le fichier complémentaire : seuls ces quatre-là
# peuvent être prolongés à partir de sa feuille "Alger 2001".
_AGRICOLE_FRAIS_DISPONIBLES = [
    ("Viandes_Abats_de_Mouton", "Viandes_Abats de Mouton"),
    ("Viandes_Abats_de_Bœufs", "Viandes_Abats de Bœufs"),
    ("Poissons_Frais", "Poissons Frais"),
    ("Pommes_de_Terre", "Pommes de Terre"),
]
AGRICOLE_FRAIS_SANS_SOURCE = [
    "Viandes_de_poulet",
    "Œufs",
    "Légumes_frais",
    "Fruits_frais",
]

_CATEGORIES = [
    ("Biens_alimentaires", "Biens alimentaires (y.c. Boiss. Alcool)"),
    ("Biens_manufacturés", "Biens manufacturés"),
    ("Services", "Services"),
]

_CORE = [
    ("Produits_alimentaires_industriels", "Produits alimentaires industriels"),
    ("Biens_manufacturés", "Biens manufacturés"),
    ("Services", "Services"),
]


def creer_feuille_core_si_absente(fichier_calculs: str, fichier_complementaire: str = None) -> bool:
    """
    Crée la feuille 'core' du fichier de travail si elle manque. Elle
    n'existe pas dans le fichier brut : sans elle, un clone neuf du projet ne
    pouvait pas exécuter pipeline_global(). Elle est reconstruite sur tout
    l'historique à partir de l'onglet 'IPC_Catégories' du fichier
    complémentaire (produits alimentaires industriels, biens manufacturés,
    services). Renvoie True si la feuille a été créée.
    """
    from config.settings import FICHIER_DONNEES_COMPLEMENTAIRES, FEUILLE_CORE

    wb = load_workbook(fichier_calculs)
    if FEUILLE_CORE in wb.sheetnames:
        wb.close()
        return False
    fichier_complementaire = fichier_complementaire or str(FICHIER_DONNEES_COMPLEMENTAIRES)
    if not os.path.exists(fichier_complementaire):
        wb.close()
        raise FileNotFoundError(
            "Feuille 'core' absente et fichier complémentaire introuvable (%s) : "
            "impossible de reconstruire le panier sous-jacent." % fichier_complementaire
        )
    source = _parser_bloc_large(fichier_complementaire, "IPC_Catégories")
    mois = sorted(
        {m for colonne, libelle in _CORE for m in source.get(_normaliser_libelle(libelle), {}).get("valeurs", {})}
    )
    ws = wb.create_sheet(FEUILLE_CORE)
    ws.append(["date"] + [colonne for colonne, _libelle in _CORE])
    for m in mois:
        valeurs = _valeurs_pour_mois(source, _CORE, m)
        ws.append([m.to_pydatetime()] + [valeurs.get(colonne) for colonne, _l in _CORE])
    wb.save(fichier_calculs)
    wb.close()
    return True


def _valeurs_pour_mois(source: dict, mapping: list, mois: pd.Timestamp) -> dict:
    """{colonne_projet: valeur} disponibles pour ce mois, selon `mapping`."""
    out = {}
    for colonne, libelle_ref in mapping:
        entree = source.get(_normaliser_libelle(libelle_ref))
        if entree is None:
            continue
        valeur = entree["valeurs"].get(mois)
        if valeur is not None:
            out[colonne] = valeur
    return out


def _lire_ipc_global(fichier_complementaire: str, feuille: str) -> dict:
    """{Timestamp (jour=1): valeur} de la ligne 'IPC Global' (niveau mensuel,
    premier bloc) d'un onglet du fichier complémentaire."""
    donnees = _parser_bloc_large(fichier_complementaire, feuille)
    entree = donnees.get(_normaliser_libelle("IPC Global"))
    if entree is None:
        raise ValueError(f"'IPC Global' introuvable dans la feuille '{feuille}'.")
    return entree["valeurs"]


def _dernier_mois_complementaire(fichier_complementaire: str) -> str:
    """Dernier mois publié dans l'onglet National_2001 ('AAAA-MM') : la borne
    de fin vient des données, jamais d'une date écrite dans le code."""
    valeurs = _lire_ipc_global(fichier_complementaire, "National_2001")
    return max(valeurs).strftime("%Y-%m")


def ingerer_ipc_national_officiel(nom_fichier: str, fichier_complementaire: str = None, date_fin: str = None):
    """
    Remplace 'IPC (%)' de la feuille 'national' par l'indice "IPC Global"
    publié tel quel dans le fichier complémentaire (onglet National_2001),
    plutôt que la moyenne pondérée recalculée à partir des huit groupes.

    Une pondération unique appliquée uniformément depuis 2002 ne capture
    pas d'éventuelles révisions historiques du panier national (constaté :
    jusqu'à ~0.9 pp d'écart avec l'officiel, concentré autour de 2009-2011,
    non résolu par un simple correctif de poids) ; l'indice officiel les
    intègre déjà. Les colonnes détaillées par groupe (Inflation_*_(%)_
    <groupe>, Contrib_*_<groupe>) restent en somme pondérée : on n'a pas
    les poids historiques pour les rendre cohérentes avec ce niveau
    officiel sur toute la période.

    N'a aucun effet si le fichier complémentaire est absent.
    """
    from config.settings import FICHIER_DONNEES_COMPLEMENTAIRES

    if fichier_complementaire is None:
        fichier_complementaire = str(FICHIER_DONNEES_COMPLEMENTAIRES)
    if date_fin is None and os.path.exists(fichier_complementaire):
        date_fin = _dernier_mois_complementaire(fichier_complementaire)
    if not os.path.exists(fichier_complementaire):
        return None

    fichier_calculs = fichier_de_travail(nom_fichier)
    niveaux = _lire_ipc_global(fichier_complementaire, "National_2001")

    wb = load_workbook(fichier_calculs)
    ws = wb["national"]
    col_index = None
    for col in range(1, ws.max_column + 1):
        if ws.cell(row=1, column=col).value == "IPC (%)":
            col_index = col
            break
    if col_index is None:
        wb.close()
        raise ValueError("Colonne 'IPC (%)' absente de la feuille 'national'.")

    for row in range(2, ws.max_row + 1):
        cell_date = ws.cell(row=row, column=1).value
        if cell_date is None:
            continue
        date_ligne = pd.Timestamp(cell_date).replace(day=1)
        valeur = niveaux.get(date_ligne)
        if valeur is not None:
            ws.cell(row=row, column=col_index, value=float(valeur))
    wb.save(fichier_calculs)
    wb.close()

    calculer_inflation_mom(fichier_calculs, "national", "2002-01", date_fin)
    calculer_inflation_yoy(fichier_calculs, "national", "2002-01", date_fin)


def etendre_historique_depuis_complementaire(
    nom_fichier: str, fichier_complementaire: str = None, date_fin: str = None
):
    """
    Complète les feuilles existantes (Grand_Alger, national, categories,
    core, Produits_agricoles_frais, Alimentations_Boissons_non_alco) avec
    les mois manquants jusqu'à `date_fin`, à partir des onglets "Alger
    2001" / "National_2001" / "IPC_Catégories" du fichier complémentaire
    (voir config.settings.FICHIER_DONNEES_COMPLEMENTAIRES).

    Quatre postes de 'Produits_agricoles_frais' n'existent pas à ce niveau
    de détail dans le fichier complémentaire (AGRICOLE_FRAIS_SANS_SOURCE) :
    leurs cellules restent vides sur les mois ajoutés, et 'IPC Non Core (%)'
    est alors repris directement de l'agrégat national "Produits agricoles
    frais" plutôt que recalculé par une somme pondérée incomplète.

    N'a aucun effet si le fichier complémentaire est absent.
    """
    from config.settings import FICHIER_DONNEES_COMPLEMENTAIRES
    from backend.inflation.data_entry import inserer_ligne_panier

    if fichier_complementaire is None:
        fichier_complementaire = str(FICHIER_DONNEES_COMPLEMENTAIRES)
    if not os.path.exists(fichier_complementaire):
        return None

    fichier_calculs = fichier_de_travail(nom_fichier)

    date_fin = date_fin or _dernier_mois_complementaire(fichier_complementaire)
    alger = _parser_bloc_large(fichier_complementaire, "Alger 2001")
    national_src = _parser_bloc_large(fichier_complementaire, "National_2001")
    categories_src = _parser_bloc_large(fichier_complementaire, "IPC_Catégories")

    date_debut = "2002-01"
    fin = pd.Period(date_fin, freq="M")

    # Le 4e élément indique si la feuille existe aussi dans le fichier BRUT
    # (nom_fichier) : 'core' n'y a jamais existé (voir fichier_de_travail).
    plan = [
        ("Grand_Alger", alger, _GROUPES_PANIER, True),
        ("national", national_src, _GROUPES_PANIER, True),
        ("categories", categories_src, _CATEGORIES, True),
        ("core", categories_src, _CORE, False),
        ("Alimentations_Boissons_non_alco", alger, _SOUS_ITEMS_ALIMENTATION, True),
        ("Produits_agricoles_frais", alger, _AGRICOLE_FRAIS_DISPONIBLES, True),
    ]

    sheets_brutes = set(pd.ExcelFile(nom_fichier).sheet_names)

    mois_ajoutes = {}
    for feuille, source, mapping, aussi_brut in plan:
        date_max = pd.Period(get_max_date(fichier_calculs, feuille), freq="M")
        depart = date_max + 1
        if depart > fin:
            mois_ajoutes[feuille] = []
            continue
        mois_manquants = [p.to_timestamp(how="start") for p in pd.period_range(depart, fin, freq="M")]
        ajoutes = []
        for mois in mois_manquants:
            valeurs = _valeurs_pour_mois(source, mapping, mois)
            if valeurs:
                inserer_ligne_panier(fichier_calculs, feuille, mois, valeurs, ecraser=False)
                if aussi_brut and feuille in sheets_brutes:
                    inserer_ligne_panier(nom_fichier, feuille, mois, valeurs, ecraser=False)
                ajoutes.append(mois)
        mois_ajoutes[feuille] = ajoutes

    # --- Garde-fou : aucune feuille ne doit dépasser `date_fin`. Une
    # anomalie ici a déjà corrompu des feuilles par le passé (des lignes à
    # 2029/2033/2041) sans qu'aucune insertion ne soit pourtant rapportée
    # ci-dessus ; mieux vaut échouer bruyamment que recalculer sur des
    # données corrompues.
    for feuille, _, _, _ in plan:
        date_verif = pd.Period(get_max_date(fichier_calculs, feuille), freq="M")
        if date_verif > fin:
            raise RuntimeError(
                f"Anomalie : la feuille '{feuille}' du fichier de calculs contient "
                f"des dates au-delà de {date_fin} (trouvé : {date_verif}). "
                "Recalcul interrompu — vérifier/nettoyer la feuille avant de relancer."
            )

    date_fin_str = fin.strftime("%Y-%m")

    # --- Recalcul : Grand Alger / national / categories (données complètes)
    for feuille in ("Grand_Alger", "categories", "national"):
        pipeline_calculs(nom_fichier, feuille, date_debut, date_fin_str)

    # --- National : IPC officiel tel quel plutôt que la moyenne pondérée
    # recalculée (voir ingerer_ipc_national_officiel).
    ingerer_ipc_national_officiel(nom_fichier, fichier_complementaire, date_fin_str)

    # --- Core / Non-Core : IPC d'abord (Non-Core restera NaN sur les mois
    # incomplets, corrigé juste après), inflation ensuite.
    calculer_ipc_core_noncore(fichier_calculs, "core", "Produits_agricoles_frais", date_debut, date_fin_str)

    # --- Corriger 'IPC Non Core (%)' avec l'agrégat national "Produits
    # agricoles frais" (même assiette de poids : 169.18) partout où la somme
    # pondérée (calculer_ipc_core_noncore, juste au-dessus) est vide faute de
    # sous-produits complets — PAS seulement sur les mois ajoutés lors de CET
    # appel : calculer_ipc_core_noncore réécrit TOUTE la colonne à chaque
    # exécution, donc un simple recalcul (sans nouvelle insertion) revide les
    # mois déjà corrigés par le passé si on ne les retraite pas à chaque fois.
    agregat = categories_src.get(_normaliser_libelle("Produits agricoles frais"))
    if agregat is not None:
        wb = load_workbook(fichier_calculs)
        ws = wb["Produits_agricoles_frais"]
        col_index = None
        for col in range(1, ws.max_column + 1):
            if ws.cell(row=1, column=col).value == "IPC Non Core (%)":
                col_index = col
                break
        if col_index is not None:
            for row in range(2, ws.max_row + 1):
                cell_date = ws.cell(row=row, column=1).value
                if cell_date is None:
                    continue
                if ws.cell(row=row, column=col_index).value is not None:
                    continue  # déjà une valeur (somme pondérée complète) : ne pas écraser
                date_ligne = pd.Timestamp(cell_date).replace(day=1)
                valeur = agregat["valeurs"].get(date_ligne)
                if valeur is not None:
                    ws.cell(row=row, column=col_index, value=float(valeur))
        wb.save(fichier_calculs)
        wb.close()

    for feuille in ("core", "Produits_agricoles_frais"):
        calculer_inflation_mom(fichier_calculs, feuille, date_debut, date_fin_str)
        calculer_inflation_yoy(fichier_calculs, feuille, date_debut, date_fin_str)

    calculer_contributions_core_noncore_mom(
        fichier_calculs, "core", "Produits_agricoles_frais", "categories", date_debut, date_fin_str
    )
    calculer_contributions_core_noncore_yoy(
        fichier_calculs, "core", "Produits_agricoles_frais", "categories", date_debut, date_fin_str
    )

    # --- Détail par sous-produit de Produits_agricoles_frais (pour le focus
    # "agricoles frais" du rapport : identifier_top_contributeurs() en a
    # besoin). Pas fait par pipeline_calculs (réservé à Grand_Alger /
    # categories / national) — ajouté ici spécifiquement.
    calculer_inflation_elements_mom(fichier_calculs, "Produits_agricoles_frais", date_debut, date_fin_str)
    calculer_inflation_elements_yoy(fichier_calculs, "Produits_agricoles_frais", date_debut, date_fin_str)
    calculer_contributions_pp_mom(fichier_calculs, "Produits_agricoles_frais", date_debut, date_fin_str)
    calculer_contributions_pp_yoy(fichier_calculs, "Produits_agricoles_frais", date_debut, date_fin_str)

    return mois_ajoutes


def extraire_inflation_mom(nom_fichier: str, nom_feuille: str, date_ref: str):
    """
    Récupère la valeur de l'inflation mensuelle (Inflation (%, mom))
    à une date donnée (année-mois), ainsi que son évolution par rapport
    au mois précédent.

    Paramètres
    ----------
    nom_fichier : str
        Chemin du fichier Excel
    nom_feuille : str
        Nom de la feuille dans le fichier Excel
    date_ref : str
        Date de référence au format 'YYYY-MM-DD' (seuls année et mois sont pris en compte)

    Retour
    ------
    tuple (str, str)
        - taux_actuel : valeur formatée à la date donnée (ex: '0.85%')
        - evolution : différence vs mois précédent (ex: '+0.23' ou '-0.45')
    """

    # Charger les données
    df = pd.read_excel(nom_fichier, sheet_name=nom_feuille, index_col=0, parse_dates=True)

    col_inflation = "Inflation (%, mom)"
    if col_inflation not in df.columns:
        raise ValueError(f"Colonne '{col_inflation}' introuvable dans {nom_feuille}")

    # Extraire année et mois
    date_ref_dt = pd.to_datetime(date_ref)
    annee, mois = date_ref_dt.year, date_ref_dt.month

    # Filtrer la ligne correspondante (mois demandé)
    mask = (df.index.year == annee) & (df.index.month == mois)
    if not mask.any():
        raise ValueError(f"Aucune donnée pour {annee}-{mois:02d} dans {nom_feuille}")

    taux_actuel = df.loc[mask, col_inflation].iloc[0]

    # Déterminer mois précédent
    if mois == 1:  # si janvier -> comparer à décembre de l'année précédente
        annee_prec, mois_prec = annee - 1, 12
    else:
        annee_prec, mois_prec = annee, mois - 1

    # Récupérer la valeur du mois précédent
    mask_prec = (df.index.year == annee_prec) & (df.index.month == mois_prec)
    if not mask_prec.any():
        raise ValueError(f"Aucune donnée pour {annee_prec}-{mois_prec:02d} (comparaison)")

    taux_precedent = df.loc[mask_prec, col_inflation].iloc[0]

    # Calcul évolution
    evolution = taux_actuel - taux_precedent

    # Formatage
    taux_actuel_fmt = f"{taux_actuel:.2f}%"
    evolution_fmt = f"{evolution:+.2f}"

    return taux_actuel_fmt, evolution_fmt


def extraire_inflation_yoy(nom_fichier: str, nom_feuille: str, date_ref: str):
    """
    Récupère la valeur de l'inflation annuelle (Inflation (%, yoy))
    à une date donnée (année-mois), ainsi que son évolution par rapport
    au même mois de l'année précédente.

    Paramètres
    ----------
    nom_fichier : str
        Chemin du fichier Excel
    nom_feuille : str
        Nom de la feuille dans le fichier Excel
    date_ref : str
        Date de référence au format 'YYYY-MM-DD' (seuls année et mois sont pris en compte)

    Retour
    ------
    tuple (str, str)
        - taux_actuel : valeur formatée à la date donnée (ex: '7.85%')
        - evolution : différence vs même mois année précédente (ex: '+0.23' ou '-0.45')
    """

    # Charger les données
    df = pd.read_excel(nom_fichier, sheet_name=nom_feuille, index_col=0, parse_dates=True)

    col_inflation = "Inflation (%, yoy)"
    if col_inflation not in df.columns:
        raise ValueError(f"Colonne '{col_inflation}' introuvable dans {nom_feuille}")

    # Conversion de la date de référence
    date_ref_dt = pd.to_datetime(date_ref)
    annee, mois = date_ref_dt.year, date_ref_dt.month

    # Filtrer la ligne correspondante (même année-mois)
    mask = (df.index.year == annee) & (df.index.month == mois)
    if not mask.any():
        raise ValueError(f"Aucune donnée pour {annee}-{mois:02d} dans {nom_feuille}")

    taux_actuel = df.loc[mask, col_inflation].iloc[0]

    # Date de comparaison : même mois année précédente
    annee_prec = annee - 1
    mask_prec = (df.index.year == annee_prec) & (df.index.month == mois)
    if not mask_prec.any():
        raise ValueError(f"Aucune donnée pour {annee_prec}-{mois:02d} (comparaison)")

    taux_precedent = df.loc[mask_prec, col_inflation].iloc[0]

    # Calcul évolution
    evolution = taux_actuel - taux_precedent

    # Formatage
    taux_actuel_fmt = f"{taux_actuel:.2f}%"
    evolution_fmt = f"{evolution:+.2f}"

    return taux_actuel_fmt, evolution_fmt


# --- Exemple d'utilisation ---
if __name__ == "__main__":
    Fichier_de_donnes = "Fichier_de_donnes.xlsx"
    pipeline_global(Fichier_de_donnes)


# ===========================================================================
# Statistiques et diagnostics servant au moteur de rédaction du rapport
# (backend/inflation/reporting.py). Ces fonctions ne calculent aucune série
# nouvelle : elles résument des colonnes déjà écrites dans le fichier de
# travail par les pipelines ci-dessus.
# ===========================================================================


def _fichier_par_defaut(nom_fichier=None) -> str:
    """Chemin du fichier de calculs, pris dans config.settings par défaut."""
    from config.settings import FICHIER_DONNEES_CALCULS

    return str(nom_fichier or FICHIER_DONNEES_CALCULS)


def _lire_indexe(nom_fichier, feuille) -> pd.DataFrame:
    """Feuille lue avec un index de dates trié."""
    df = pd.read_excel(_fichier_par_defaut(nom_fichier), sheet_name=feuille)
    df.rename(columns={df.columns[0]: "date"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date"]).set_index("date").sort_index()


def _ligne_du_mois(df: pd.DataFrame, date_ref):
    """
    Ligne correspondant au mois de `date_ref`.

    Les dates du fichier ne tombent pas sur le premier du mois : on apparie
    sur l'année et le mois, jamais sur le jour.
    """
    date_ref = pd.to_datetime(date_ref)
    masque = (df.index.year == date_ref.year) & (df.index.month == date_ref.month)
    if not masque.any():
        raise ValueError("Aucune donnée pour %d-%02d dans cette feuille" % (date_ref.year, date_ref.month))
    return df.loc[masque].iloc[0]


def calculer_statistiques_historiques(
    nom_fichier, feuille: str, colonne: str, date_debut=None, date_fin=None, periode_reference: str = None
) -> dict:
    """
    Résume une colonne sur la période demandée.

    `periode_reference="post_2015"` restreint le calcul au régime récent, afin
    de calibrer les seuils du moteur de rédaction sans laisser les régimes
    anciens peser sur la moyenne et l'écart-type.

    Retour : {"moyenne", "ecart_type", "min", "max", "nb_observations"}
    """
    df = _lire_indexe(nom_fichier, feuille)
    if colonne not in df.columns:
        raise ValueError("Colonne '%s' introuvable dans la feuille '%s'" % (colonne, feuille))

    if periode_reference and date_debut is None:
        from config.settings import NARRATIVE_RULES_PATH

        with open(NARRATIVE_RULES_PATH, "r", encoding="utf-8") as flux:
            regles = json.load(flux)
        date_debut = regles.get("periode_reference_statistiques", {}).get(periode_reference)

    serie = df[colonne]
    if date_debut is not None:
        serie = serie.loc[pd.Timestamp(date_debut) :]
    if date_fin is not None:
        serie = serie.loc[: pd.Timestamp(date_fin) + pd.offsets.MonthEnd(1)]

    serie = serie.dropna()
    if serie.empty:
        return {"moyenne": None, "ecart_type": None, "min": None, "max": None, "nb_observations": 0}

    return {
        "moyenne": round(float(serie.mean()), 3),
        "ecart_type": round(float(serie.std(ddof=1)), 3) if len(serie) > 1 else 0.0,
        "min": round(float(serie.min()), 3),
        "max": round(float(serie.max()), 3),
        "nb_observations": int(serie.size),
    }


def calculer_moyenne_ytd(nom_fichier, feuille: str, colonne: str, annee: int):
    """
    Moyenne de l'indicateur de janvier de `annee` jusqu'à la dernière donnée
    disponible de cette même année. Renvoie None si l'année n'est pas couverte.
    """
    df = _lire_indexe(nom_fichier, feuille)
    if colonne not in df.columns:
        raise ValueError("Colonne '%s' introuvable dans la feuille '%s'" % (colonne, feuille))

    serie = df.loc[df.index.year == int(annee), colonne].dropna()
    if serie.empty:
        return None
    return round(float(serie.mean()), 3)


def calculer_moyenne_ytd_comparee(nom_fichier, feuille: str, colonne: str, date_reference):
    """
    Moyenne YTD (janvier -> mois de `date_reference`) pour l'année de
    `date_reference`, et la même fenêtre de mois l'année précédente — pour
    comparer des moyennes réellement comparables (pas 12 mois complets
    contre une fraction d'année).

    Retour : (moyenne_actuelle, moyenne_annee_precedente), chacune pouvant
    être None si l'année correspondante n'a pas de données sur la fenêtre.
    """
    df = _lire_indexe(nom_fichier, feuille)
    if colonne not in df.columns:
        raise ValueError("Colonne '%s' introuvable dans la feuille '%s'" % (colonne, feuille))

    date_reference = pd.Timestamp(date_reference)
    mois_limite = date_reference.month

    def _moyenne(annee):
        serie = df.loc[(df.index.year == annee) & (df.index.month <= mois_limite), colonne].dropna()
        return round(float(serie.mean()), 3) if not serie.empty else None

    return _moyenne(date_reference.year), _moyenne(date_reference.year - 1)


def taux_variation_colonne(nom_fichier, feuille: str, colonne: str, date_ref, mode: str = "yoy"):
    """
    Variation (%) d'une colonne d'INDICE BRUTE (pas une colonne d'inflation
    déjà calculée) entre `date_ref` et le mois précédent (mode='mom') ou le
    même mois l'an dernier (mode='yoy').

    Sert aux séries qui n'ont pas de colonne 'Inflation (%, ...)' dédiée —
    ex. 'Produits_alimentaires_industriels' dans la feuille 'core', qui
    n'existe qu'au travers de l'agrégat 'IPC Core (%)'.

    Retour : le taux en %, ou None si l'un des deux mois manque.
    """
    if mode not in ("mom", "yoy"):
        raise ValueError("mode doit valoir 'mom' ou 'yoy'")

    df = _lire_indexe(nom_fichier, feuille)
    if colonne not in df.columns:
        raise ValueError("Colonne '%s' introuvable dans la feuille '%s'" % (colonne, feuille))

    ligne = _ligne_du_mois(df, date_ref)
    date_actuelle = ligne.name
    decalage = 1 if mode == "mom" else 12
    date_precedente = date_actuelle - pd.DateOffset(months=decalage)

    valeur_actuelle = ligne.get(colonne)
    masque_prec = (df.index.year == date_precedente.year) & (df.index.month == date_precedente.month)
    if pd.isna(valeur_actuelle) or not masque_prec.any():
        return None

    valeur_precedente_base = df.loc[masque_prec, colonne].iloc[0]
    if pd.isna(valeur_precedente_base) or valeur_precedente_base == 0:
        return None

    taux = (float(valeur_actuelle) / float(valeur_precedente_base) - 1) * 100
    return round(taux, 2)


def serie_variation_colonne(
    nom_fichier, feuille: str, colonne: str, date_fin, mode: str = "yoy", nb_points: int = 12
) -> pd.Series:
    """
    Version "série" de taux_variation_colonne() : le taux de variation (%)
    d'une colonne d'indice brute, un point par mois, sur les `nb_points`
    derniers mois jusqu'à `date_fin`. Sert aux graphiques de décomposition
    du rapport pour les colonnes sans 'Inflation (%, ...)' dédiée (ex.
    'Produits_alimentaires_industriels' dans 'core').
    """
    if mode not in ("mom", "yoy"):
        raise ValueError("mode doit valoir 'mom' ou 'yoy'")

    df = _lire_indexe(nom_fichier, feuille)
    if colonne not in df.columns:
        raise ValueError("Colonne '%s' introuvable dans la feuille '%s'" % (colonne, feuille))

    decalage = 1 if mode == "mom" else 12
    serie_valeurs = df[colonne].astype(float)
    taux = (serie_valeurs / serie_valeurs.shift(decalage) - 1) * 100

    date_fin = pd.Timestamp(date_fin)
    mois = pd.period_range(end=date_fin.to_period("M"), periods=nb_points, freq="M")
    resultat = {}
    for periode in mois:
        masque = (taux.index.year == periode.year) & (taux.index.month == periode.month)
        valeur = taux.loc[masque]
        resultat[periode.to_timestamp(how="start")] = (
            round(float(valeur.iloc[0]), 2) if not valeur.empty and pd.notna(valeur.iloc[0]) else None
        )
    return pd.Series(resultat)


def serie_moyenne_annuelle_glissante(
    nom_fichier, feuille: str, colonne: str, date_fin, nb_points: int = 12
) -> pd.Series:
    """
    Pour chacun des `nb_points` derniers mois jusqu'à `date_fin` inclus, la
    moyenne de l'indicateur depuis janvier de l'année de ce mois jusqu'à ce
    mois (moyenne YTD glissante — cf. calculer_moyenne_ytd, mais un point
    par mois plutôt qu'un point unique). Sert au graphique "moyenne
    annuelle" du rapport (Figure 2).

    Retour : pd.Series indexée par Timestamp (premier du mois), en %.
    """
    df = _lire_indexe(nom_fichier, feuille)
    if colonne not in df.columns:
        raise ValueError("Colonne '%s' introuvable dans la feuille '%s'" % (colonne, feuille))

    date_fin = pd.Timestamp(date_fin)
    mois = pd.period_range(end=date_fin.to_period("M"), periods=nb_points, freq="M")

    valeurs = {}
    for periode in mois:
        debut_annee = pd.Timestamp(year=periode.year, month=1, day=1)
        fin_mois = periode.to_timestamp(how="end")
        fenetre = df.loc[debut_annee:fin_mois, colonne].dropna()
        valeurs[periode.to_timestamp(how="start")] = round(float(fenetre.mean()), 3) if not fenetre.empty else None

    return pd.Series(valeurs)


def _colonnes_contributions(df: pd.DataFrame, mode: str):
    """Colonnes de contribution du mode demandé, avec leur libellé lisible."""
    prefixe = "Contrib_MoM_" if mode == "mom" else "Contrib_YoY_"
    suffixe = " (pp)"
    # Contrib_Core_* et Contrib_Non_Core_* sont des agrégats, pas des éléments
    # du panier : les inclure fausserait la somme des contributions.
    agregats = ("Contrib_Core_", "Contrib_Non_Core_")

    resultat = []
    for colonne in df.columns:
        nom = str(colonne)
        if not nom.startswith(prefixe) or nom.startswith(agregats):
            continue
        libelle = nom[len(prefixe) :]
        if libelle.endswith(suffixe):
            libelle = libelle[: -len(suffixe)]
        resultat.append((nom, libelle.replace("_", " ").strip()))
    return resultat


def identifier_top_contributeurs(nom_fichier, feuille: str, date, mode: str = "mom", n: int = 3):
    """
    Plus forts contributeurs positifs et négatifs à une date donnée.

    Retour : tuple (positifs, negatifs), deux listes de dicts
    {"nom", "contribution", "part"}, triées par valeur absolue décroissante.
    `part` est la part du poste dans la masse des contributions du mois, en %
    (voir le commentaire sur le dénominateur plus bas).
    """
    if mode not in ("mom", "yoy"):
        raise ValueError("mode doit valoir 'mom' ou 'yoy'")

    df = _lire_indexe(nom_fichier, feuille)
    colonnes = _colonnes_contributions(df, mode)
    if not colonnes:
        raise ValueError("Aucune colonne de contribution %s dans la feuille '%s'" % (mode.upper(), feuille))

    ligne = _ligne_du_mois(df, date)
    valeurs = []
    for colonne, libelle in colonnes:
        valeur = ligne.get(colonne)
        if pd.isna(valeur):
            continue
        valeurs.append((libelle, float(valeur)))

    # Classement et part du mouvement (dénominateur = masse des contributions,
    # voir backend.common.statistiques.classer_contributeurs) : logique
    # partagée avec le module PIB.
    from backend.common.statistiques import classer_contributeurs

    return classer_contributeurs(valeurs, n=n)


def verifier_coherence_contributions(nom_fichier, feuille: str, date, mode: str, tolerance: float = 0.1):
    """
    Vérifie que la somme des contributions en pp reproduit bien l'inflation du
    panier à `tolerance` pp près.

    Retour : tuple (coherent, ecart_constate). L'écart est signé : somme des
    contributions moins inflation.
    """
    if mode not in ("mom", "yoy"):
        raise ValueError("mode doit valoir 'mom' ou 'yoy'")

    df = _lire_indexe(nom_fichier, feuille)
    colonne_inflation = "Inflation (%, mom)" if mode == "mom" else "Inflation (%, yoy)"
    if colonne_inflation not in df.columns:
        raise ValueError("Colonne '%s' introuvable dans '%s'" % (colonne_inflation, feuille))

    ligne = _ligne_du_mois(df, date)
    inflation = ligne.get(colonne_inflation)
    if pd.isna(inflation):
        return False, float("nan")

    somme = 0.0
    for colonne, _libelle in _colonnes_contributions(df, mode):
        valeur = ligne.get(colonne)
        if not pd.isna(valeur):
            somme += float(valeur)

    ecart = round(somme - float(inflation), 3)
    return bool(abs(ecart) <= tolerance), ecart


# ===========================================================================
# Pondérations déclarées (config/weights.json), utilisées par le rapport.
# ===========================================================================


def _poids_bruts(feuille: str) -> dict:
    """Pondérations de la feuille, telles que déclarées dans weights.json."""
    from config.settings import WEIGHTS_PATH

    with open(WEIGHTS_PATH, "r", encoding="utf-8") as flux:
        tous = json.load(flux)
    if feuille not in tous:
        raise ValueError("Aucune pondération pour la feuille « %s »" % feuille)
    from backend.common.excel_io import extraire_poids

    return extraire_poids(tous[feuille])


def derniere_inflation(nom_fichier, feuille: str, colonne: str = "Inflation (%, yoy)"):
    """
    Dernière valeur publiée de `colonne`, son écart au MOIS PRÉCÉDENT (en
    points) et sa date. Pour l'accueil : extraire_inflation_yoy() renvoie,
    elle, un écart au même mois de l'an dernier.
    """
    serie = _lire_indexe(nom_fichier, feuille)[colonne].dropna()
    if serie.empty:
        return None
    delta = float(serie.iloc[-1] - serie.iloc[-2]) if len(serie) > 1 else None
    return float(serie.iloc[-1]), delta, serie.index[-1]
