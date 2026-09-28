import os
import json
import pandas as pd
import plotly.graph_objects as go
import locale
import zipfile
from config.settings import FICHIER_DONNEES_CALCULS, CATEGORIES_PATH


def safe_read_excel(path, **kwargs):
    """Lit un fichier Excel, même s'il est contenu dans un .zip"""
    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            # prendre le premier .xlsx trouvé
            for name in z.namelist():
                if name.endswith(".xlsx") or name.endswith(".xls"):
                    with z.open(name) as f:
                        return pd.read_excel(f, engine="openpyxl", **kwargs)
        raise FileNotFoundError("Aucun .xlsx trouvé dans le zip")
    else:
        return pd.read_excel(path, engine="openpyxl", **kwargs)


def _pas_affichage(n_points: int) -> int:
    """
    Nombre de mois entre deux graduations de l'axe X, adapté à la longueur
    de la période affichée. Un pas fixe (ex. un point sur trois) devient
    illisible sur un historique long (des dizaines de graduations qui se
    chevauchent, plus aucun mois lisible) et inutilement clairsemé sur une
    courte période.
    """
    if n_points <= 24:
        return 1
    if n_points <= 60:
        return 3
    if n_points <= 120:
        return 6
    return 12


def tracer_inflation_dashboard_yoy(
    nom_fichier: str,
    feuille_categories: str,
    feuille_core: str,
    feuille_non_core: str,
    date_debut: str,
    date_fin: str,
    export_png: bool = True,
):
    """
    Trace un graphique interactif (Plotly) de l'inflation IPC, Core et Non Core.
    Affiche le résultat dans Streamlit et enregistre une copie PNG si demandé.
    """

    # --- 1. Construire le chemin du fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 2. Lire les résultats calculés
    df_global = safe_read_excel(fichier_calculs, sheet_name=feuille_categories, index_col=0, parse_dates=True)
    df_core = safe_read_excel(fichier_calculs, sheet_name=feuille_core, index_col=0, parse_dates=True)
    df_noncore = safe_read_excel(fichier_calculs, sheet_name=feuille_non_core, index_col=0, parse_dates=True)

    # --- 3. Trouver la colonne "Inflation (%, yoy)"
    def trouver_colonne_yoy(cols):
        cible = "Inflation (%, yoy)"
        for col in cols:
            if col.strip() == cible:
                return col
        return None

    col_global = trouver_colonne_yoy(df_global.columns)
    col_core = trouver_colonne_yoy(df_core.columns)
    col_noncore = trouver_colonne_yoy(df_noncore.columns)

    if not col_global or not col_core or not col_noncore:
        raise ValueError("Impossible de trouver la colonne exacte 'Inflation (%, yoy)' dans l'un des fichiers Excel.")

    # --- 4. Gérer les bornes de dates
    first_valid_date = max(
        df_global.first_valid_index(),
        df_core.first_valid_index(),
        df_noncore.first_valid_index(),
    )

    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)

    real_start = max(first_valid_date, date_debut_dt)

    df_global = df_global.loc[real_start:date_fin_dt]
    df_core = df_core.loc[real_start:date_fin_dt]
    df_noncore = df_noncore.loc[real_start:date_fin_dt]

    # --- 5. Axe X avec labels en FR

    x = df_global.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")  # Ex: janv. 2023

    # --- 6. Création du graphique interactif
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=df_global[col_global],
            mode="lines+markers",
            name="Inflation IPC",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC: %{y:.2f}%",
            text=x_labels,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=df_core[col_core],
            mode="lines+markers",
            name="Inflation Core",
            line=dict(color="#ff7f0e", width=2.0, dash="dash"),
            hovertemplate="Date: %{text}<br>Core: %{y:.2f}%",
            text=x_labels,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=df_noncore[col_noncore],
            mode="lines+markers",
            name="Inflation Non Core",
            line=dict(color="#2ca02c", width=2.0, dash="dot"),
            hovertemplate="Date: %{text}<br>Non Core: %{y:.2f}%",
            text=x_labels,
        )
    )

    # Ligne horizontale cible
    fig.add_hline(y=4, line_dash="dash", line_color="red", annotation_text="Cible 4%", annotation_position="top right")

    # Habillage
    fig.update_layout(
        title="Inflation IPC, core et non_core (%) - YoY",
        xaxis_title="Date",
        yaxis_title="Inflation annuelle (%)",
        template="plotly_white",
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=600,
    )

    fig.update_yaxes(ticksuffix=" %")

    # Alléger l'axe X → un tick par trimestre
    fig.update_xaxes(
        tickmode="array", tickvals=x[:: _pas_affichage(len(x))], ticktext=x_labels[:: _pas_affichage(len(x))]
    )

    # --- 7. Affichage Streamlit

    # --- 8. Export PNG pour rapport
    # --- 7. Export PNG pour rapport
    if export_png:
        # Créer le dossier 'graphes' s'il n'existe pas
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)

        # Définir le chemin complet du fichier
        output_png = os.path.join(dossier_graphes, "inflation_core_noncore_yoy.png")

        # Sauvegarder l'image
        fig.write_image(output_png, width=1200, height=600, scale=2)

    return fig


def tracer_inflation_dashboard_mom(
    nom_fichier: str,
    feuille_categories: str,
    feuille_core: str,
    feuille_non_core: str,
    date_debut: str,
    date_fin: str,
    export_png: bool = True,
):
    """
    Trace un graphique interactif (Plotly) de l'inflation IPC, Core et Non Core en glissement mensuel (MoM).
    Les axes sont alignés pour que Core/Non-Core et IPC soient comparables.
    """

    # --- 1. Construire le chemin du fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 2. Lire les résultats calculés
    df_global = pd.read_excel(fichier_calculs, sheet_name=feuille_categories, index_col=0, parse_dates=True)
    df_core = pd.read_excel(fichier_calculs, sheet_name=feuille_core, index_col=0, parse_dates=True)
    df_noncore = pd.read_excel(fichier_calculs, sheet_name=feuille_non_core, index_col=0, parse_dates=True)

    # --- 3. Trouver la colonne "Inflation (%, mom)"
    def trouver_colonne_mom(cols):
        cible = "Inflation (%, mom)"
        for col in cols:
            if col.strip() == cible:
                return col
        return None

    col_global = trouver_colonne_mom(df_global.columns)
    col_core = trouver_colonne_mom(df_core.columns)
    col_noncore = trouver_colonne_mom(df_noncore.columns)

    if not col_global or not col_core or not col_noncore:
        raise ValueError("Impossible de trouver la colonne exacte 'Inflation (%, mom)' dans l'un des fichiers Excel.")

    # --- 4. Gérer les bornes de dates
    first_valid_date = max(
        df_global.first_valid_index(),
        df_core.first_valid_index(),
        df_noncore.first_valid_index(),
    )

    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)

    real_start = max(first_valid_date, date_debut_dt)

    df_global = df_global.loc[real_start:date_fin_dt]
    df_core = df_core.loc[real_start:date_fin_dt]
    df_noncore = df_noncore.loc[real_start:date_fin_dt]

    # --- 5. Axe X avec labels en FR

    x = df_global.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Création du graphique interactif
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=df_global[col_global],
            mode="lines+markers",
            name="Inflation IPC (MoM)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC MoM: %{y:.2f}%",
            text=x_labels,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=df_core[col_core],
            mode="lines+markers",
            name="Inflation Core (MoM)",
            line=dict(color="#ff7f0e", width=2.0, dash="dash"),
            hovertemplate="Date: %{text}<br>Core MoM: %{y:.2f}%",
            text=x_labels,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=df_noncore[col_noncore],
            mode="lines+markers",
            name="Inflation Non Core (MoM)",
            line=dict(color="#2ca02c", width=2.0, dash="dot"),
            hovertemplate="Date: %{text}<br>Non Core MoM: %{y:.2f}%",
            text=x_labels,
        )
    )

    # --- 7. Habillage
    fig.update_layout(
        title="Inflation IPC, core et non_core (%) - MoM",
        xaxis_title="Date",
        yaxis=dict(title="Inflation mensuelle (%)", ticksuffix=" %"),
        template="plotly_white",
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=600,
    )

    # Tick X un par trimestre
    fig.update_xaxes(
        tickmode="array", tickvals=x[:: _pas_affichage(len(x))], ticktext=x_labels[:: _pas_affichage(len(x))]
    )

    # --- 8. Affichage Streamlit

    # --- 9. Export PNG pour rapport
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_core_noncore_mom.png")
        fig.write_image(output_png, width=1200, height=600, scale=2)

    return fig


def _tracer_indices_complementaires(
    nom_fichier: str,
    feuille_national: str,
    feuille_reglementes: str,
    feuille_fci: str,
    feuille_core2: str,
    date_debut: str,
    date_fin: str,
    mode: str,
    export_png: bool,
):
    """
    Fonction commune à tracer_indices_complementaires_yoy / _mom : indice
    national global (référence, en gris) et les trois indices nationaux
    complémentaires (Réglementés, FCI, Core 2 = inflation sous-jacente 2).
    """
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)
    colonne = "Inflation (%, yoy)" if mode == "yoy" else "Inflation (%, mom)"

    series = [
        ("Inflation IPC (national)", feuille_national),
        ("Réglementés", feuille_reglementes),
        ("Fort contenu d'import (FCI)", feuille_fci),
        ("Sous-jacente 2 (hors réglementés, hors agricole frais)", feuille_core2),
    ]

    dfs = {}
    for _, feuille in series:
        df = safe_read_excel(fichier_calculs, sheet_name=feuille, index_col=0, parse_dates=True)
        if colonne not in df.columns:
            raise ValueError(f"Colonne '{colonne}' introuvable dans la feuille '{feuille}'.")
        dfs[feuille] = df

    first_valid_date = max(df[colonne].first_valid_index() for df in dfs.values())
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)
    real_start = max(first_valid_date, date_debut_dt)

    for feuille in dfs:
        dfs[feuille] = dfs[feuille].loc[real_start:date_fin_dt]

    x = dfs[feuille_national].index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    fig = go.Figure()
    dash_styles = [None, "dash", "dot"]
    for i, (nom, feuille) in enumerate(series):
        df = dfs[feuille]
        ligne = dict(width=2.4 if i == 0 else 2.0)
        if i > 0:
            ligne["dash"] = dash_styles[i - 1] if i - 1 < len(dash_styles) else "dot"
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df[colonne],
                mode="lines+markers",
                name=nom,
                line=ligne,
                hovertemplate="Date: %{text}<br>" + nom + ": %{y:.2f}%",
                text=x_labels,
            )
        )

    suffixe = "YoY" if mode == "yoy" else "MoM"
    fig.update_layout(
        title=f"Indices nationaux complémentaires — Réglementés, FCI, sous-jacente 2 ({suffixe})",
        xaxis_title="Date",
        yaxis=dict(title=f"Inflation {'annuelle' if mode == 'yoy' else 'mensuelle'} (%)", ticksuffix=" %"),
        template="plotly_white",
        legend=dict(title="", orientation="h", y=1.15, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=600,
    )
    fig.update_xaxes(
        tickmode="array", tickvals=x[:: _pas_affichage(len(x))], ticktext=x_labels[:: _pas_affichage(len(x))]
    )

    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, f"indices_complementaires_nationaux_{mode}.png")
        fig.write_image(output_png, width=1200, height=600, scale=2)

    return fig


def tracer_indices_complementaires_yoy(
    nom_fichier: str,
    feuille_national: str,
    feuille_reglementes: str,
    feuille_fci: str,
    feuille_core2: str,
    date_debut: str,
    date_fin: str,
    export_png: bool = True,
):
    """Inflation YoY : indice national, Réglementés, FCI, sous-jacente 2."""
    return _tracer_indices_complementaires(
        nom_fichier,
        feuille_national,
        feuille_reglementes,
        feuille_fci,
        feuille_core2,
        date_debut,
        date_fin,
        mode="yoy",
        export_png=export_png,
    )


def tracer_indices_complementaires_mom(
    nom_fichier: str,
    feuille_national: str,
    feuille_reglementes: str,
    feuille_fci: str,
    feuille_core2: str,
    date_debut: str,
    date_fin: str,
    export_png: bool = True,
):
    """Inflation MoM : indice national, Réglementés, FCI, sous-jacente 2."""
    return _tracer_indices_complementaires(
        nom_fichier,
        feuille_national,
        feuille_reglementes,
        feuille_fci,
        feuille_core2,
        date_debut,
        date_fin,
        mode="mom",
        export_png=export_png,
    )


def tracer_contributions_core_noncore_yoy(
    nom_fichier: str, feuille_categories: str, date_debut: str, date_fin: str, export_png: bool = True
):

    # --- 1. Chemin du fichier
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 2. Lire les données
    df = pd.read_excel(fichier_calculs, sheet_name=feuille_categories, index_col=0, parse_dates=True)

    colonnes_requises = ["Inflation (%, yoy)", "Contrib_Core_YoY (pp)", "Contrib_Non_Core_YoY (pp)"]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante : '{col}'")

    # --- 3. Bornes de dates
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)
    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 4. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 5. Calcul plage y commune
    min_val = min(
        df["Inflation (%, yoy)"].min(), df["Contrib_Core_YoY (pp)"].min(), df["Contrib_Non_Core_YoY (pp)"].min()
    )
    max_val = max(
        df["Inflation (%, yoy)"].max(), df["Contrib_Core_YoY (pp)"].max(), df["Contrib_Non_Core_YoY (pp)"].max()
    )

    buffer = (max_val - min_val) * 0.1  # marge 10%
    y_range = [min_val - buffer, max_val + buffer]

    # --- 6. Graphique
    fig = go.Figure()

    # Ligne IPC
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, yoy)"],
            mode="lines+markers",
            name="Inflation IPC",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Barres Core et Non-Core sur le même axe Y
    fig.add_trace(
        go.Bar(
            x=x,
            y=df["Contrib_Core_YoY (pp)"],
            name="Contribution Core",
            marker_color="#ff7f0e",
            hovertemplate="Date: %{x|%b %Y}<br>Core: %{y:.2f} pp",
        )
    )

    fig.add_trace(
        go.Bar(
            x=x,
            y=df["Contrib_Non_Core_YoY (pp)"],
            name="Contribution Non-Core",
            marker_color="#2ca02c",
            hovertemplate="Date: %{x|%b %Y}<br>Non-Core: %{y:.2f} pp",
        )
    )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et contributions core & non_core (YoY)",
        xaxis=dict(
            title="Date",
            tickmode="array",
            tickvals=x[:: _pas_affichage(len(x))],
            ticktext=x_labels[:: _pas_affichage(len(x))],
        ),
        yaxis=dict(title="Inflation & Contributions (pp / %)", range=y_range),
        template="plotly_white",
        barmode="relative",  # stack mais négatif sous zéro
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=600,
    )

    # --- 8. Affichage Streamlit

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "contributions_inflation_core_noncore_yoy.png")
        fig.write_image(output_png, width=1200, height=600, scale=2)

    return fig


def tracer_contributions_core_noncore_mom(
    nom_fichier: str, feuille_categories: str, date_debut: str, date_fin: str, export_png: bool = True
):

    # --- 1. Chemin du fichier
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 2. Lire les données
    df = pd.read_excel(fichier_calculs, sheet_name=feuille_categories, index_col=0, parse_dates=True)

    colonnes_requises = ["Inflation (%, mom)", "Contrib_Core_MoM (pp)", "Contrib_Non_Core_MoM (pp)"]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante : '{col}'")

    # --- 3. Bornes de dates
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)
    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 4. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 5. Calcul plage y commune
    min_val = min(
        df["Inflation (%, mom)"].min(), df["Contrib_Core_MoM (pp)"].min(), df["Contrib_Non_Core_MoM (pp)"].min()
    )
    max_val = max(
        df["Inflation (%, mom)"].max(), df["Contrib_Core_MoM (pp)"].max(), df["Contrib_Non_Core_MoM (pp)"].max()
    )
    buffer = (max_val - min_val) * 0.1
    y_range = [min_val - buffer, max_val + buffer]

    # --- 6. Graphique
    fig = go.Figure()

    # Ligne IPC
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, mom)"],
            mode="lines+markers",
            name="Inflation IPC (MoM)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC MoM: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Barres Core et Non-Core sur le même axe Y
    fig.add_trace(
        go.Bar(
            x=x,
            y=df["Contrib_Core_MoM (pp)"],
            name="Contribution Core",
            marker_color="#ff7f0e",
            hovertemplate="Date: %{x|%b %Y}<br>Core: %{y:.2f} pp",
        )
    )

    fig.add_trace(
        go.Bar(
            x=x,
            y=df["Contrib_Non_Core_MoM (pp)"],
            name="Contribution Non-Core",
            marker_color="#2ca02c",
            hovertemplate="Date: %{x|%b %Y}<br>Non-Core: %{y:.2f} pp",
        )
    )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et contributions core & non_core (MoM)",
        xaxis=dict(
            title="Date",
            tickmode="array",
            tickvals=x[:: _pas_affichage(len(x))],
            ticktext=x_labels[:: _pas_affichage(len(x))],
        ),
        yaxis=dict(title="Inflation & Contributions (pp / %)", range=y_range),
        template="plotly_white",
        barmode="relative",
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=600,
    )

    # --- 8. Affichage Streamlit

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "contributions_inflation_core_noncore_mom.png")
        fig.write_image(output_png, width=1200, height=600, scale=2)

    return fig


def tracer_inflation_grand_alger_mom(nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True):
    """
    Trace l'inflation IPC mensuelle (MoM) du Grand Alger
    ainsi que les 8 éléments du panier (définis dans config/categories.json).
    """

    # --- 1. Charger la config JSON (chemin intégré)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Les 8 éléments du panier
    elements_panier = config.get("Grand_Alger", [])

    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json")

    # --- 2. Construire le chemin du fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Lire les données Excel
    df = pd.read_excel(fichier_calculs, sheet_name="Grand_Alger", index_col=0, parse_dates=True)

    # Vérification des colonnes
    colonnes_requises = ["Inflation (%, mom)"] + [f"Inflation_MoM (%)_{cat}" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Gestion des bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)

    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique interactif
    fig = go.Figure()

    # IPC global
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, mom)"],
            mode="lines+markers",
            name="Inflation IPC (MoM)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Les 8 éléments du panier
    couleurs = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]

    for i, cat in enumerate(elements_panier):
        col_name = f"Inflation_MoM (%)_{cat}"
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df[col_name],
                mode="lines+markers",
                name=cat,
                line=dict(width=2.0, dash="dot", color=couleurs[i % len(couleurs)]),
                hovertemplate=f"Date: %{{text}}<br>{cat}: %{{y:.2f}} %",
                text=x_labels,
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et Composantes du Panier (MoM) - Grand Alger",
        xaxis_title="Date",
        yaxis_title="Inflation mensuelle (%)",
        template="plotly_white",
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # Axe Y en pourcentage
    fig.update_yaxes(ticksuffix=" %")

    # Alléger l'axe X → 1 tick par trimestre
    fig.update_xaxes(
        tickmode="array", tickvals=x[:: _pas_affichage(len(x))], ticktext=x_labels[:: _pas_affichage(len(x))]
    )

    # --- 8. Affichage

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_grand_alger_mom.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


def tracer_inflation_grand_alger_yoy(nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True):
    """
    Trace l'inflation IPC annuelle (YoY) du Grand Alger
    ainsi que les 8 éléments du panier (définis dans config/categories.json).
    """

    # --- 1. Charger la config JSON (chemin intégré)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Les 8 éléments du panier
    elements_panier = config.get("Grand_Alger", [])

    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json")

    # --- 2. Construire le chemin du fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Lire les données Excel
    df = pd.read_excel(fichier_calculs, sheet_name="Grand_Alger", index_col=0, parse_dates=True)

    # Vérification des colonnes
    colonnes_requises = ["Inflation (%, yoy)"] + [f"Inflation_YoY (%)_{cat}" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Gestion des bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)

    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique interactif
    fig = go.Figure()

    # IPC global
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, yoy)"],
            mode="lines+markers",
            name="Inflation IPC (YoY)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Les 8 éléments du panier
    couleurs = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]

    for i, cat in enumerate(elements_panier):
        col_name = f"Inflation_YoY (%)_{cat}"
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df[col_name],
                mode="lines+markers",
                name=cat,
                line=dict(width=2.0, dash="dot", color=couleurs[i % len(couleurs)]),
                hovertemplate=f"Date: %{{text}}<br>{cat}: %{{y:.2f}} %",
                text=x_labels,
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et Composantes du Panier (YoY) - Grand Alger",
        xaxis_title="Date",
        yaxis_title="Inflation annuelle (%)",
        template="plotly_white",
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # Axe Y en pourcentage
    fig.update_yaxes(ticksuffix=" %")

    # Alléger l'axe X → 1 tick par trimestre
    fig.update_xaxes(
        tickmode="array", tickvals=x[:: _pas_affichage(len(x))], ticktext=x_labels[:: _pas_affichage(len(x))]
    )

    # --- 8. Affichage

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_grand_alger_yoy.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


def tracer_inflation_contributions_grand_alger_mom(
    nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True
):
    """
    Trace l'inflation IPC (MoM) + contributions des éléments du panier (barres).
    """

    # --- 1. Charger config JSON (catégories)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    elements_panier = config.get("Grand_Alger", [])
    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json")

    # --- 2. Construire chemin fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Charger données
    df = pd.read_excel(fichier_calculs, sheet_name="Grand_Alger", index_col=0, parse_dates=True)

    colonnes_requises = ["Inflation (%, mom)"] + [f"Contrib_MoM_{cat} (pp)" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)
    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique
    fig = go.Figure()

    # Ligne IPC
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, mom)"],
            mode="lines+markers",
            name="Inflation IPC (MoM)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC MoM: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Barres des contributions des 8 éléments
    couleurs = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]

    for i, cat in enumerate(elements_panier):
        col_name = f"Contrib_MoM_{cat} (pp)"
        fig.add_trace(
            go.Bar(
                x=x,
                y=df[col_name],
                name=cat,
                marker_color=couleurs[i % len(couleurs)],
                hovertemplate=f"Date: %{{x|%b %Y}}<br>{cat}: %{{y:.2f}} pp",
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et Contributions des Composantes - Grand Alger (MoM)",
        xaxis=dict(
            title="Date",
            tickmode="array",
            tickvals=x[:: _pas_affichage(len(x))],
            ticktext=x_labels[:: _pas_affichage(len(x))],
        ),
        yaxis=dict(title="Inflation & Contributions (pp / %)", ticksuffix=" %"),
        template="plotly_white",
        barmode="relative",  # empilement
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # --- 8. Affichage Streamlit

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_contributions_grand_alger_mom.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


def tracer_inflation_contributions_grand_alger_yoy(
    nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True
):
    """
    Trace l'inflation IPC (MoM) + contributions des éléments du panier (barres).
    """

    # --- 1. Charger config JSON (catégories)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    elements_panier = config.get("Grand_Alger", [])
    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json")

    # --- 2. Construire chemin fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Charger données
    df = pd.read_excel(fichier_calculs, sheet_name="Grand_Alger", index_col=0, parse_dates=True)

    colonnes_requises = ["Inflation (%, yoy)"] + [f"Contrib_YoY_{cat} (pp)" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)
    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique
    fig = go.Figure()

    # Ligne IPC
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, yoy)"],
            mode="lines+markers",
            name="Inflation IPC (YoY)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC MoM: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Barres des contributions des 8 éléments
    couleurs = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]

    for i, cat in enumerate(elements_panier):
        col_name = f"Contrib_YoY_{cat} (pp)"
        fig.add_trace(
            go.Bar(
                x=x,
                y=df[col_name],
                name=cat,
                marker_color=couleurs[i % len(couleurs)],
                hovertemplate=f"Date: %{{x|%b %Y}}<br>{cat}: %{{y:.2f}} pp",
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et Contributions des Composantes - Grand Alger (YoY)",
        xaxis=dict(
            title="Date",
            tickmode="array",
            tickvals=x[:: _pas_affichage(len(x))],
            ticktext=x_labels[:: _pas_affichage(len(x))],
        ),
        yaxis=dict(title="Inflation & Contributions (pp / %)", ticksuffix=" %"),
        template="plotly_white",
        barmode="relative",  # empilement
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # --- 8. Affichage Streamlit

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_contributions_grand_alger_yoy.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


def tracer_inflation_national_mom(nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True):
    """
    Trace l'inflation IPC mensuelle (MoM) du National
    ainsi que les 8 éléments du panier (définis dans config/categories.json).
    """

    # --- 1. Charger la config JSON (chemin intégré)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Les 8 éléments du panier
    elements_panier = config.get("national", [])

    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json")

    # --- 2. Construire le chemin du fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Lire les données Excel
    df = pd.read_excel(fichier_calculs, sheet_name="national", index_col=0, parse_dates=True)

    # Vérification des colonnes
    colonnes_requises = ["Inflation (%, mom)"] + [f"Inflation_MoM (%)_{cat}" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Gestion des bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)

    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique interactif
    fig = go.Figure()

    # IPC global
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, mom)"],
            mode="lines+markers",
            name="Inflation IPC (MoM)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Les 8 éléments du panier
    couleurs = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]

    for i, cat in enumerate(elements_panier):
        col_name = f"Inflation_MoM (%)_{cat}"
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df[col_name],
                mode="lines+markers",
                name=cat,
                line=dict(width=2.0, dash="dot", color=couleurs[i % len(couleurs)]),
                hovertemplate=f"Date: %{{text}}<br>{cat}: %{{y:.2f}} %",
                text=x_labels,
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et Composantes du Panier (MoM) - National",
        xaxis_title="Date",
        yaxis_title="Inflation mensuelle (%)",
        template="plotly_white",
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # Axe Y en pourcentage
    fig.update_yaxes(ticksuffix=" %")

    # Alléger l'axe X → 1 tick par trimestre
    fig.update_xaxes(
        tickmode="array", tickvals=x[:: _pas_affichage(len(x))], ticktext=x_labels[:: _pas_affichage(len(x))]
    )

    # --- 8. Affichage

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_national_mom.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


def tracer_inflation_national_yoy(nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True):
    """
    Trace l'inflation IPC annuelle (YoY) du National
    ainsi que les 8 éléments du panier (définis dans config/categories.json).
    """

    # --- 1. Charger la config JSON (chemin intégré)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Les 8 éléments du panier
    elements_panier = config.get("national", [])

    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json")

    # --- 2. Construire le chemin du fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Lire les données Excel
    df = pd.read_excel(fichier_calculs, sheet_name="national", index_col=0, parse_dates=True)

    # Vérification des colonnes
    colonnes_requises = ["Inflation (%, yoy)"] + [f"Inflation_YoY (%)_{cat}" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Gestion des bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)

    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique interactif
    fig = go.Figure()

    # IPC global
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, yoy)"],
            mode="lines+markers",
            name="Inflation IPC (YoY)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Les 8 éléments du panier
    couleurs = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]

    for i, cat in enumerate(elements_panier):
        col_name = f"Inflation_YoY (%)_{cat}"
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df[col_name],
                mode="lines+markers",
                name=cat,
                line=dict(width=2.0, dash="dot", color=couleurs[i % len(couleurs)]),
                hovertemplate=f"Date: %{{text}}<br>{cat}: %{{y:.2f}} %",
                text=x_labels,
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et Composantes du Panier (YoY) - National",
        xaxis_title="Date",
        yaxis_title="Inflation annuelle (%)",
        template="plotly_white",
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # Axe Y en pourcentage
    fig.update_yaxes(ticksuffix=" %")

    # Alléger l'axe X → 1 tick par trimestre
    fig.update_xaxes(
        tickmode="array", tickvals=x[:: _pas_affichage(len(x))], ticktext=x_labels[:: _pas_affichage(len(x))]
    )

    # --- 8. Affichage

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_national_yoy.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


def tracer_inflation_contributions_national_mom(
    nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True
):
    """
    Trace l'inflation IPC (MoM) + contributions des éléments du panier (barres).
    """

    # --- 1. Charger config JSON (catégories)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    elements_panier = config.get("national", [])
    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json")

    # --- 2. Construire chemin fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Charger données
    df = pd.read_excel(fichier_calculs, sheet_name="national", index_col=0, parse_dates=True)

    colonnes_requises = ["Inflation (%, mom)"] + [f"Contrib_MoM_{cat} (pp)" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)
    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique
    fig = go.Figure()

    # Ligne IPC
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, mom)"],
            mode="lines+markers",
            name="Inflation IPC (MoM)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC MoM: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Barres des contributions des 8 éléments
    couleurs = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]

    for i, cat in enumerate(elements_panier):
        col_name = f"Contrib_MoM_{cat} (pp)"
        fig.add_trace(
            go.Bar(
                x=x,
                y=df[col_name],
                name=cat,
                marker_color=couleurs[i % len(couleurs)],
                hovertemplate=f"Date: %{{x|%b %Y}}<br>{cat}: %{{y:.2f}} pp",
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et Contributions des Composantes - National (MoM)",
        xaxis=dict(
            title="Date",
            tickmode="array",
            tickvals=x[:: _pas_affichage(len(x))],
            ticktext=x_labels[:: _pas_affichage(len(x))],
        ),
        yaxis=dict(title="Inflation & Contributions (pp / %)", ticksuffix=" %"),
        template="plotly_white",
        barmode="relative",  # empilement
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # --- 8. Affichage Streamlit

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_contributions_national_mom.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


def tracer_inflation_contributions_national_yoy(
    nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True
):
    """
    Trace l'inflation IPC (MoM) + contributions des éléments du panier (barres).
    """

    # --- 1. Charger config JSON (catégories)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    elements_panier = config.get("national", [])
    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json")

    # --- 2. Construire chemin fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Charger données
    df = pd.read_excel(fichier_calculs, sheet_name="national", index_col=0, parse_dates=True)

    colonnes_requises = ["Inflation (%, mom)"] + [f"Contrib_YoY_{cat} (pp)" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)
    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique
    fig = go.Figure()

    # Ligne IPC
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, yoy)"],
            mode="lines+markers",
            name="Inflation IPC (YoY)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC MoM: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Barres des contributions des 8 éléments
    couleurs = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]

    for i, cat in enumerate(elements_panier):
        col_name = f"Contrib_YoY_{cat} (pp)"
        fig.add_trace(
            go.Bar(
                x=x,
                y=df[col_name],
                name=cat,
                marker_color=couleurs[i % len(couleurs)],
                hovertemplate=f"Date: %{{x|%b %Y}}<br>{cat}: %{{y:.2f}} pp",
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et Contributions des Composantes - National (YOY)",
        xaxis=dict(
            title="Date",
            tickmode="array",
            tickvals=x[:: _pas_affichage(len(x))],
            ticktext=x_labels[:: _pas_affichage(len(x))],
        ),
        yaxis=dict(title="Inflation & Contributions (pp / %)", ticksuffix=" %"),
        template="plotly_white",
        barmode="relative",  # empilement
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # --- 8. Affichage Streamlit

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_contributions_national_yoy.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


def tracer_inflation_categories_mom(nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True):
    """
    Trace l'inflation IPC mensuelle (MoM) du panier 'categories'
    ainsi que ses 3 éléments (définis dans config/categories.json).
    """

    # --- 1. Charger la config JSON (chemin intégré)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Les 3 éléments du panier "categories"
    elements_panier = config.get("categories", [])

    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json pour 'categories'")

    # --- 2. Construire le chemin du fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Lire les données Excel
    df = pd.read_excel(fichier_calculs, sheet_name="categories", index_col=0, parse_dates=True)

    # Vérification des colonnes
    colonnes_requises = ["Inflation (%, mom)"] + [f"Inflation_MoM (%)_{cat}" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Gestion des bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)

    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique interactif
    fig = go.Figure()

    # IPC global du panier "categories"
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, mom)"],
            mode="lines+markers",
            name="Inflation IPC (MoM)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Les 3 éléments du panier
    couleurs = ["#e41a1c", "#377eb8", "#4daf4a"]  # palette spéciale 3 couleurs

    for i, cat in enumerate(elements_panier):
        col_name = f"Inflation_MoM (%)_{cat}"
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df[col_name],
                mode="lines+markers",
                name=cat,
                line=dict(width=2.0, dash="dot", color=couleurs[i]),
                hovertemplate=f"Date: %{{text}}<br>{cat}: %{{y:.2f}} %",
                text=x_labels,
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et des composantes par catégories (MoM)",
        xaxis_title="Date",
        yaxis_title="Inflation mensuelle (%)",
        template="plotly_white",
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # Axe Y en pourcentage
    fig.update_yaxes(ticksuffix=" %")

    # Alléger l'axe X → 1 tick par trimestre
    fig.update_xaxes(
        tickmode="array", tickvals=x[:: _pas_affichage(len(x))], ticktext=x_labels[:: _pas_affichage(len(x))]
    )

    # --- 8. Affichage

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_catégories_mom.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


def tracer_inflation_categories_yoy(nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True):
    """
    Trace l'inflation IPC mensuelle (MoM) du panier 'categories'
    ainsi que ses 3 éléments (définis dans config/categories.json).
    """

    # --- 1. Charger la config JSON (chemin intégré)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Les 3 éléments du panier "categories"
    elements_panier = config.get("categories", [])

    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json pour 'categories'")

    # --- 2. Construire le chemin du fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Lire les données Excel
    df = pd.read_excel(fichier_calculs, sheet_name="categories", index_col=0, parse_dates=True)

    # Vérification des colonnes
    colonnes_requises = ["Inflation (%, yoy)"] + [f"Inflation_YoY (%)_{cat}" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Gestion des bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)

    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique interactif
    fig = go.Figure()

    # IPC global du panier "categories"
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, yoy)"],
            mode="lines+markers",
            name="Inflation IPC (YoY)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Les 3 éléments du panier
    couleurs = ["#e41a1c", "#377eb8", "#4daf4a"]  # palette spéciale 3 couleurs

    for i, cat in enumerate(elements_panier):
        col_name = f"Inflation_YoY (%)_{cat}"
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df[col_name],
                mode="lines+markers",
                name=cat,
                line=dict(width=2.0, dash="dot", color=couleurs[i]),
                hovertemplate=f"Date: %{{text}}<br>{cat}: %{{y:.2f}} %",
                text=x_labels,
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et des composantes par catégories (YoY)",
        xaxis_title="Date",
        yaxis_title="Inflation annuelle (%)",
        template="plotly_white",
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # Axe Y en pourcentage
    fig.update_yaxes(ticksuffix=" %")

    # Alléger l'axe X → 1 tick par trimestre
    fig.update_xaxes(
        tickmode="array", tickvals=x[:: _pas_affichage(len(x))], ticktext=x_labels[:: _pas_affichage(len(x))]
    )

    # --- 8. Affichage

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_catégories_yoy.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


def tracer_inflation_contributions_categories_mom(
    nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True
):
    """
    Trace l'inflation IPC (MoM) + contributions des éléments du panier (barres).
    """

    # --- 1. Charger config JSON (catégories)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    elements_panier = config.get("categories", [])
    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json")

    # --- 2. Construire chemin fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Charger données
    df = pd.read_excel(fichier_calculs, sheet_name="categories", index_col=0, parse_dates=True)

    colonnes_requises = ["Inflation (%, mom)"] + [f"Contrib_MoM_{cat} (pp)" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)
    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR
    try:
        locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, "French_France.1252")
        except locale.Error:
            pass  # locale FR indisponible : libelles de mois en anglais

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique
    fig = go.Figure()

    # Ligne IPC
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, mom)"],
            mode="lines+markers",
            name="Inflation IPC (MoM)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC MoM: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Barres des contributions des 8 éléments
    couleurs = ["#e41a1c", "#377eb8", "#4daf4a"]

    for i, cat in enumerate(elements_panier):
        col_name = f"Contrib_MoM_{cat} (pp)"
        fig.add_trace(
            go.Bar(
                x=x,
                y=df[col_name],
                name=cat,
                marker_color=couleurs[i % len(couleurs)],
                hovertemplate=f"Date: %{{x|%b %Y}}<br>{cat}: %{{y:.2f}} pp",
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et Contributions des Composantes - Catégories (MoM)",
        xaxis=dict(
            title="Date",
            tickmode="array",
            tickvals=x[:: _pas_affichage(len(x))],
            ticktext=x_labels[:: _pas_affichage(len(x))],
        ),
        yaxis=dict(title="Inflation & Contributions (pp / %)", ticksuffix=" %"),
        template="plotly_white",
        barmode="relative",  # empilement
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # --- 8. Affichage Streamlit

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_contributions_catégories_mom.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


def tracer_inflation_contributions_categories_yoy(
    nom_fichier: str, date_debut: str, date_fin: str, export_png: bool = True
):
    """
    Trace l'inflation IPC (MoM) + contributions des éléments du panier (barres).
    """

    # --- 1. Charger config JSON (catégories)
    chemin_json = str(CATEGORIES_PATH)

    if not os.path.exists(chemin_json):
        raise FileNotFoundError(f"❌ Fichier JSON introuvable : {chemin_json}")

    with open(chemin_json, "r", encoding="utf-8") as f:
        config = json.load(f)

    elements_panier = config.get("categories", [])
    if not elements_panier:
        raise ValueError("❌ Aucune catégorie trouvée dans config/categories.json")

    # --- 2. Construire chemin fichier enrichi
    fichier_calculs = str(FICHIER_DONNEES_CALCULS)

    # --- 3. Charger données
    df = pd.read_excel(fichier_calculs, sheet_name="categories", index_col=0, parse_dates=True)

    colonnes_requises = ["Inflation (%, yoy)"] + [f"Contrib_YoY_{cat} (pp)" for cat in elements_panier]
    for col in colonnes_requises:
        if col not in df.columns:
            raise ValueError(f"❌ Colonne manquante dans Excel : {col}")

    # --- 4. Bornes temporelles
    first_valid_date = df.first_valid_index()
    date_debut_dt = pd.to_datetime(date_debut)
    date_fin_dt = pd.to_datetime(date_fin) + pd.offsets.MonthEnd(1)
    real_start = max(first_valid_date, date_debut_dt)
    df = df.loc[real_start:date_fin_dt]

    # --- 5. Axe X FR

    x = df.index.to_period("M").to_timestamp(how="start")
    x_labels = x.strftime("%b %Y")

    # --- 6. Graphique
    fig = go.Figure()

    # Ligne IPC
    fig.add_trace(
        go.Scatter(
            x=x,
            y=df["Inflation (%, yoy)"],
            mode="lines+markers",
            name="Inflation IPC (YoY)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Date: %{text}<br>IPC YoY: %{y:.2f} %",
            text=x_labels,
        )
    )

    # Barres des contributions des 8 éléments
    couleurs = ["#e41a1c", "#277eb8", "#4daf4a"]

    for i, cat in enumerate(elements_panier):
        col_name = f"Contrib_YoY_{cat} (pp)"
        fig.add_trace(
            go.Bar(
                x=x,
                y=df[col_name],
                name=cat,
                marker_color=couleurs[i % len(couleurs)],
                hovertemplate=f"Date: %{{x|%b %Y}}<br>{cat}: %{{y:.2f}} pp",
            )
        )

    # --- 7. Layout
    fig.update_layout(
        title="Inflation IPC et Contributions des Composantes - Catégories (YoY)",
        xaxis=dict(
            title="Date",
            tickmode="array",
            tickvals=x[:: _pas_affichage(len(x))],
            ticktext=x_labels[:: _pas_affichage(len(x))],
        ),
        yaxis=dict(title="Inflation & Contributions (pp / %)", ticksuffix=" %"),
        template="plotly_white",
        barmode="relative",  # empilement
        legend=dict(title="", orientation="h", y=1.1, x=0.5, xanchor="center"),
        hovermode="x unified",
        height=700,
    )

    # --- 8. Affichage Streamlit

    # --- 9. Export PNG
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        output_png = os.path.join(dossier_graphes, "inflation_contributions_catégories_yoy.png")
        fig.write_image(output_png, width=1200, height=700, scale=2)

    return fig


# Communes étiquetées en mode Grand Alger : quelques repères lisibles, pas
# les 57 (illisible sans zoom).
COMMUNES_ETIQUETEES = [
    "Alger-Centre",
    "Bab El Oued",
    "Hussein Dey",
    "El Harrach",
    "Bab Ezzouar",
    "Chéraga",
    "Zeralda",
    "Rouiba",
    "Birtouta",
    "Draria",
]


def _geojson(nom):
    """Fond de carte embarqué (assets/geo/), lu une seule fois par processus."""
    import json
    from functools import lru_cache
    from config.settings import GEO_DIR

    @lru_cache(maxsize=None)
    def _lire(n):
        with open(GEO_DIR / n, "r", encoding="utf-8") as flux:
            return json.load(flux)

    return _lire(nom)


def _projeter(lon, lat0):
    """Équirectangulaire centrée sur `lat0` : distances justes à ces latitudes."""
    import math

    return lon * math.cos(math.radians(lat0))


def _trace_polygones(geojson, lat0, remplissage, contour, largeur, survol, nom):
    """Tous les polygones d'un GeoJSON en une seule trace Scatter (anneaux séparés par None)."""
    xs, ys, textes = [], [], []
    for f in geojson["features"]:
        geometrie = f["geometry"]
        polygones = [geometrie["coordinates"]] if geometrie["type"] == "Polygon" else geometrie["coordinates"]
        for poly in polygones:
            for x, y in poly[0]:
                xs.append(_projeter(x, lat0))
                ys.append(y)
                textes.append(f["properties"].get("nom", ""))
            xs.append(None)
            ys.append(None)
            textes.append(None)
    return go.Scatter(
        x=xs,
        y=ys,
        mode="lines",
        name=nom,
        meta="couleur_fixe",
        text=textes,
        line=dict(color=contour, width=largeur),
        fill="toself" if remplissage else None,
        fillcolor=remplissage,
        hoveron="fills" if survol else None,
        hovertemplate=survol + "<extra></extra>" if survol and "<extra>" not in survol else survol,
        hoverinfo=None if survol else "skip",
        showlegend=False,
    )


def tracer_carte_scope(portee: str, taux_pct: float, evolution_pp: float, date_ref, mode: str = "yoy") -> go.Figure:
    """
    Carte de la portée géographique, entièrement hors ligne (fonds GeoJSON
    embarqués dans assets/geo/, voir scripts/preparer_fonds_de_carte.py) :

      - National    : tout le pays, contour en or, indice national en
                      évidence, aucun repère sur Alger ;
      - Grand Alger : cadrage sur la wilaya d'Alger, contour en or, les 57
                      communes en fond sobre, une dizaine étiquetées, indice
                      Grand Alger en évidence.

    L'indice n'est publié qu'à ces deux échelles : la carte situe la portée,
    ce n'est pas un choroplèthe.
    """
    from config.branding import (
        COLOR_NAVY_DEEP,
        COLOR_NAVY_LIGHT,
        COLOR_GOLD,
        COLOR_POSITIF,
        COLOR_NEGATIF,
        COLOR_TEXTE,
        COLOR_TEXTE_ATTENUE,
    )

    est_alger = portee.strip().lower().startswith("grand alger")
    hausse = evolution_pp >= 0
    # Hausse de l'inflation = défavorable : rouge.
    couleur_delta = COLOR_NEGATIF if hausse else COLOR_POSITIF
    fleche = "▲" if hausse else "▼"
    libelle_mode = "annuelle" if mode == "yoy" else "mensuelle"
    mois = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    date_ref = pd.Timestamp(date_ref)
    date_txt = mois[date_ref.month - 1] + " " + str(date_ref.year)
    valeur_txt = ("%.2f %%" % taux_pct).replace(".", ",")
    delta_txt = ("%.2f pp" % abs(evolution_pp)).replace(".", ",")
    survol = (
        "<b>"
        + portee
        + "</b><br>Inflation "
        + libelle_mode
        + " : "
        + valeur_txt
        + "<br>Évolution : "
        + fleche
        + " "
        + delta_txt
        + "<br>"
        + date_txt
        + "<extra></extra>"
    )

    fig = go.Figure()
    if est_alger:
        communes = _geojson("alger_communes.geojson")
        fig.add_trace(
            _trace_polygones(
                communes,
                lat0=36.7,
                remplissage=COLOR_NAVY_LIGHT,
                contour="rgba(159,179,194,0.40)",
                largeur=0.7,
                survol="%{text}",
                nom="Communes",
            )
        )
        fig.add_trace(
            _trace_polygones(
                _geojson("alger_wilaya.geojson"),
                lat0=36.7,
                remplissage=None,
                contour=COLOR_GOLD,
                largeur=2.4,
                survol=None,
                nom=portee,
            )
        )
        etiquetees = [f["properties"] for f in communes["features"] if f["properties"]["nom"] in COMMUNES_ETIQUETEES]
        fig.add_trace(
            go.Scatter(
                x=[_projeter(c["lon"], 36.7) for c in etiquetees],
                y=[c["lat"] for c in etiquetees],
                mode="markers+text",
                text=[c["nom"] for c in etiquetees],
                textposition="top center",
                marker=dict(size=4, color=COLOR_TEXTE_ATTENUE),
                textfont=dict(color=COLOR_TEXTE, size=10, family="Inter, sans-serif"),
                hoverinfo="skip",
                showlegend=False,
                name="Repères",
                meta="couleur_fixe",
            )
        )
    else:
        fig.add_trace(
            _trace_polygones(
                _geojson("algerie.geojson"),
                lat0=28.0,
                remplissage=COLOR_NAVY_LIGHT,
                contour=COLOR_GOLD,
                largeur=2.4,
                survol=survol,
                nom=portee,
            )
        )

    # Repère cartésien à échelle égale : aucune couche géographique de
    # plotly (elles téléchargent un fond depuis un CDN), la carte est donc
    # entièrement hors ligne, à l'écran comme à l'export PNG.
    # Le quart gauche est réservé au cartouche : la carte ne passe jamais dessous.
    fig.update_xaxes(visible=False, scaleanchor="y", scaleratio=1, domain=[0.28, 1])
    fig.update_yaxes(visible=False)
    # Cartouche en trois annotations empilées : plotly gère mal les tailles
    # de police mélangées dans une même annotation (lignes superposées).
    cadre = dict(
        xref="paper",
        yref="paper",
        x=0.01,
        xanchor="left",
        yanchor="bottom",
        showarrow=False,
        align="left",
        font=dict(family="Inter, sans-serif"),
    )
    fig.add_shape(
        type="rect",
        xref="paper",
        yref="paper",
        x0=0.0,
        x1=0.27,
        y0=0.02,
        y1=0.30,
        fillcolor="rgba(8,31,51,0.85)",
        line=dict(color=COLOR_GOLD, width=1),
        layer="above",
    )
    fig.add_annotation(
        text="<b>" + portee + "</b>",
        y=0.22,
        **dict(cadre, font=dict(family="Inter, sans-serif", size=13, color=COLOR_TEXTE)),
    )
    fig.add_annotation(
        text="<b>"
        + valeur_txt
        + "</b>  <span style='font-size:13px;color:"
        + couleur_delta
        + "'>"
        + fleche
        + " "
        + delta_txt
        + "</span>",
        y=0.11,
        **dict(cadre, font=dict(family="Inter, sans-serif", size=22, color=COLOR_GOLD)),
    )
    fig.add_annotation(
        text="Inflation " + libelle_mode + " · " + date_txt,
        y=0.04,
        **dict(cadre, font=dict(family="Inter, sans-serif", size=11, color=COLOR_TEXTE_ATTENUE)),
    )
    fig.update_layout(
        title=dict(text="Portée géographique — " + portee),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=40, b=0),
        height=380,
        showlegend=False,
        hovermode="closest",
        hoverlabel=dict(
            bgcolor=COLOR_NAVY_DEEP, bordercolor=COLOR_GOLD, font=dict(family="Inter, sans-serif", color=COLOR_TEXTE)
        ),
    )
    return fig


# ===========================================================================
# Graphiques du rapport mensuel — fenêtre fixe de 12 mois (voir
# backend.inflation.reporting). Contrairement aux graphiques du dashboard,
# la profondeur n'est jamais un paramètre utilisateur ici.
# ===========================================================================


def _lire_serie_colonne(nom_fichier, feuille, colonne, date_fin, nb_points=12):
    """Les `nb_points` derniers mois d'une colonne déjà présente dans la
    feuille (ex. 'Inflation (%, yoy)'), en pd.Series indexée par mois."""
    df = safe_read_excel(nom_fichier, sheet_name=feuille, index_col=0, parse_dates=True)
    if colonne not in df.columns:
        raise ValueError(f"Colonne '{colonne}' introuvable dans la feuille '{feuille}'.")
    date_fin = pd.Timestamp(date_fin)
    mois = pd.period_range(end=date_fin.to_period("M"), periods=nb_points, freq="M")
    resultat = {}
    for periode in mois:
        masque = (df.index.year == periode.year) & (df.index.month == periode.month)
        valeur = df.loc[masque, colonne]
        resultat[periode.to_timestamp(how="start")] = (
            float(valeur.iloc[0]) if not valeur.empty and pd.notna(valeur.iloc[0]) else None
        )
    return pd.Series(resultat)


def _tracer_series_multiples(series_nommees, titre, suffixe_y="  %", hauteur=520):
    """
    `series_nommees` : liste de (nom, pd.Series) — déjà les valeurs à
    tracer, une par mois. L'axe X reprend l'union des mois rencontrés (12
    dans tous les usages du rapport) ; chaque tick est affiché, la fenêtre
    étant volontairement courte.
    """
    tous_index = sorted(set().union(*[serie.index for _, serie in series_nommees]))
    x = pd.DatetimeIndex(tous_index)
    x_labels = x.strftime("%b %Y")

    fig = go.Figure()
    dash_styles = ["dash", "dot", "dashdot", "longdash"]
    for i, (nom, serie) in enumerate(series_nommees):
        y = [serie.get(d) for d in x]
        ligne = dict(width=2.6 if i == 0 else 2.0)
        if i > 0:
            ligne["dash"] = dash_styles[(i - 1) % len(dash_styles)]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines+markers",
                name=nom,
                line=ligne,
                connectgaps=False,
                hovertemplate="Date: %{x|%b %Y}<br>" + nom + f": %{{y:.2f}}{suffixe_y}",
            )
        )

    # Pas de titre Plotly ici : avec 5 séries, la légende occupe déjà deux
    # rangées au-dessus du tracé, et un titre Plotly se superposait à la
    # légende (aucune réservation de hauteur automatique entre les deux).
    # Le titre est affiché par le gabarit HTML (légende sous l'image), pas
    # gravé dans le PNG.
    fig.update_layout(
        xaxis_title="Date",
        yaxis=dict(ticksuffix=suffixe_y),
        template="plotly_white",
        legend=dict(title="", orientation="h", y=1.02, x=0.5, xanchor="center", yanchor="bottom"),
        hovermode="x unified",
        margin=dict(t=70),
        height=hauteur,
    )
    fig.update_xaxes(tickmode="array", tickvals=x, ticktext=x_labels)
    return fig


def _exporter_png(fig, export_png, nom_fichier_png):
    if export_png:
        from config.settings import GRAPHES_DIR as dossier_graphes

        os.makedirs(dossier_graphes, exist_ok=True)
        fig.write_image(os.path.join(dossier_graphes, nom_fichier_png), width=1200, height=650, scale=2)


def tracer_decomposition_yoy_rapport(
    nom_fichier: str,
    feuille_national: str,
    feuille_agricole_frais: str,
    feuille_core: str,
    feuille_reglementes: str,
    feuille_core2: str,
    date_fin,
    export_png: bool = False,
) -> go.Figure:
    """
    Figure 1 du rapport : décomposition de l'inflation en glissement annuel
    — IPC global, agricoles frais, hors agricoles frais (sous-jacente 1),
    réglementés, hors réglementés et hors agricoles frais (sous-jacente 2).
    Fenêtre fixe : les 12 derniers mois.
    """
    colonne = "Inflation (%, yoy)"
    series = [
        ("IPC global (national)", _lire_serie_colonne(nom_fichier, feuille_national, colonne, date_fin)),
        ("Agricoles frais", _lire_serie_colonne(nom_fichier, feuille_agricole_frais, colonne, date_fin)),
        ("Sous-jacente 1 (hors agricoles frais)", _lire_serie_colonne(nom_fichier, feuille_core, colonne, date_fin)),
        ("Réglementés", _lire_serie_colonne(nom_fichier, feuille_reglementes, colonne, date_fin)),
        (
            "Sous-jacente 2 (hors réglementés, hors agricole frais)",
            _lire_serie_colonne(nom_fichier, feuille_core2, colonne, date_fin),
        ),
    ]
    fig = _tracer_series_multiples(series, "Décomposition de l'inflation — glissement annuel (12 derniers mois)")
    _exporter_png(fig, export_png, "rapport_decomposition_yoy.png")
    return fig


def tracer_decomposition_moyenne_annuelle_rapport(
    nom_fichier: str, feuille_national: str, feuille_core: str, feuille_core2: str, date_fin, export_png: bool = False
) -> go.Figure:
    """
    Figure 2 du rapport : IPC global, sous-jacente 1, sous-jacente 2, en
    moyenne annuelle glissante (moyenne YTD, un point par mois). Fenêtre
    fixe : les 12 derniers mois.
    """
    from backend.inflation.calculator import serie_moyenne_annuelle_glissante as _serie_ytd

    colonne = "Inflation (%, yoy)"
    series = [
        ("IPC global (national)", _serie_ytd(nom_fichier, feuille_national, colonne, date_fin)),
        ("Sous-jacente 1 (hors agricoles frais)", _serie_ytd(nom_fichier, feuille_core, colonne, date_fin)),
        (
            "Sous-jacente 2 (hors réglementés, hors agricole frais)",
            _serie_ytd(nom_fichier, feuille_core2, colonne, date_fin),
        ),
    ]
    fig = _tracer_series_multiples(series, "Inflation en moyenne annuelle (12 derniers mois)")
    _exporter_png(fig, export_png, "rapport_decomposition_moyenne_annuelle.png")
    return fig


def tracer_decomposition_mom_rapport(
    nom_fichier: str,
    feuille_agricole_frais: str,
    feuille_core: str,
    feuille_categories: str,
    feuille_national: str,
    date_fin,
    export_png: bool = False,
) -> go.Figure:
    """
    Figure 3 du rapport : agricoles frais, alimentaires industriels,
    biens manufacturés, services, IPC global — en glissement mensuel.
    Fenêtre fixe : les 12 derniers mois.

    'Manufacturés' et 'Services' viennent des colonnes 'Inflation_MoM (%)_*'
    déjà calculées sur la feuille 'categories'. 'Alimentaires industriels'
    n'a pas d'équivalent (composante de 'core', exposée seulement via
    l'agrégat 'IPC Core (%)') : calculé à la volée depuis sa colonne
    d'indice brute.
    """
    from backend.inflation.calculator import serie_variation_colonne as _serie_brute

    colonne_infl = "Inflation (%, mom)"
    series = [
        ("IPC global (national)", _lire_serie_colonne(nom_fichier, feuille_national, colonne_infl, date_fin)),
        ("Agricoles frais", _lire_serie_colonne(nom_fichier, feuille_agricole_frais, colonne_infl, date_fin)),
        (
            "Alimentaires industriels",
            _serie_brute(nom_fichier, feuille_core, "Produits_alimentaires_industriels", date_fin, mode="mom"),
        ),
        (
            "Biens manufacturés",
            _lire_serie_colonne(nom_fichier, feuille_categories, "Inflation_MoM (%)_Biens_manufacturés", date_fin),
        ),
        ("Services", _lire_serie_colonne(nom_fichier, feuille_categories, "Inflation_MoM (%)_Services", date_fin)),
    ]
    fig = _tracer_series_multiples(series, "Décomposition de l'inflation — glissement mensuel (12 derniers mois)")
    _exporter_png(fig, export_png, "rapport_decomposition_mom.png")
    return fig
