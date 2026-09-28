"""
Charte graphique du tableau de bord — Banque d'Algérie.

Point UNIQUE de définition du style. Principe directeur : une source de
lumière unique, en haut de l'écran. Toute surface est éclairée du même côté
(filet clair sur l'arête supérieure, ombre longue portée vers le bas), et l'or
n'est jamais un aplat : c'est un filet, une arête, une signature.
"""

import streamlit as st

from config.branding import (
    COLOR_NAVY_DARKEST,
    COLOR_NAVY_DEEP,
    COLOR_NAVY_LIGHT,
    COLOR_GOLD,
    COLOR_GOLD_LIGHT,
    COLOR_GOLD_DARK,
    COLOR_CYAN,
    COLOR_CYAN_MID,
    COLOR_CYAN_LIGHT,
    COLOR_POSITIF,
    COLOR_NEGATIF,
    COLOR_TEXTE,
    COLOR_TEXTE_ATTENUE,
    PALETTE_SERIES,
    INSTITUTION,
    SITE_OFFICIEL,  # noqa: F401 (ré-exporté pour les pages)
)

# ---------------------------------------------------------------------------
# 1. Palette institutionnelle — définie dans config/branding.py, partagée
#    avec le rapport PDF. Les alias ci-dessous gardent les noms courts
#    utilisés partout dans l'interface.
# ---------------------------------------------------------------------------

NAVY_DARKEST = COLOR_NAVY_DARKEST
NAVY_DEEP = COLOR_NAVY_DEEP
NAVY_LIGHT = COLOR_NAVY_LIGHT

GOLD = COLOR_GOLD
GOLD_LIGHT = COLOR_GOLD_LIGHT
GOLD_DARK = COLOR_GOLD_DARK

CYAN = COLOR_CYAN
CYAN_MID = COLOR_CYAN_MID
CYAN_LIGHT = COLOR_CYAN_LIGHT

POSITIF = COLOR_POSITIF
NEGATIF = COLOR_NEGATIF

TEXTE = COLOR_TEXTE
TEXTE_ATTENUE = COLOR_TEXTE_ATTENUE

CARTE_FOND = "rgba(255, 255, 255, 0.035)"
CARTE_BORDURE = "rgba(188, 158, 110, 0.25)"

COULEUR_AGREGAT = TEXTE
GRILLE = "rgba(159, 179, 194, 0.10)"

# PALETTE_SERIES, INSTITUTION et SITE_OFFICIEL viennent de config.branding et
# restent importables depuis ce module par les pages.


# ---------------------------------------------------------------------------
# 3. Configuration de page
# ---------------------------------------------------------------------------


def configurer_page(titre, module=None, icone=None):
    """
    À appeler en TOUT PREMIER dans chaque page. Le titre d'onglet commence
    par le libellé exact de la page, suivi du module et de l'institution.
    """
    st.set_page_config(
        page_title=titre + (" · " + module if module else "") + " — " + INSTITUTION,
        page_icon=icone,
        layout="wide",
        initial_sidebar_state="collapsed",
    )


# ---------------------------------------------------------------------------
# 4. Feuille de style globale
# ---------------------------------------------------------------------------

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');

/* ============ MODE SOMBRE FORCÉ ============ */
/* color-scheme indique au navigateur de peindre SES propres éléments
   (champs, listes, barres de défilement, sélection) en sombre. Sans lui,
   l'affichage correct dépendait du réglage du système de l'utilisateur. */
:root, html, body, .stApp { color-scheme: dark !important; }
::selection { background: rgba(188,158,110,.32); color: #FFF; }
* { scrollbar-color: rgba(188,158,110,.45) rgba(255,255,255,.05); }

/* ============ FOND : trois couches de lumière ============ */
.stApp {
    background:
        radial-gradient(ellipse 70% 42% at 50% -6%, rgba(188,158,110,0.10), transparent 68%),
        radial-gradient(ellipse 95% 60% at 50% 96%, rgba(8,122,156,0.20), transparent 66%),
        linear-gradient(180deg, __NAVY_DARKEST__ 0%, __NAVY_DEEP__ 52%, __NAVY_LIGHT__ 100%);
    background-attachment: fixed;
    font-family: 'Inter', sans-serif;
    color: __TEXTE__;
}

/* ============ Aucune barre latérale : la navigation est dans la page ============ */
section[data-testid="stSidebar"] { display: none !important; }
div[data-testid="stSidebarNav"] { display: none !important; }
div[data-testid="collapsedControl"] { display: none !important; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; height: 0; }
div[data-testid="stDecoration"] { display: none; }
/* Bouton « Deploy » et barre d'outils Streamlit : hors charte */
div[data-testid="stToolbar"], .stAppDeployButton,
div[data-testid="stStatusWidget"] { display: none !important; }

/* ============ Rythme de la page ============ */
/* La largeur utile est plafonnée pour ne pas étirer les lignes de texte sur
   un 2560, et les marges se resserrent sur les écrans étroits : aucun zoom
   navigateur ne doit être nécessaire pour lire la page. */
div.block-container {
    max-width: 1620px;
    padding: 1.6rem clamp(1rem, 2.2vw, 2.8rem) 3.5rem clamp(1rem, 2.2vw, 2.8rem);
}

/* Les graphiques suivent la largeur du conteneur, jamais une largeur fixe. */
div[data-testid="stPlotlyChart"], div[data-testid="stPlotlyChart"] > div {
    width: 100% !important;
    max-width: 100% !important;
}
div[data-testid="stDataFrame"] { max-width: 100% !important; }
img { max-width: 100%; height: auto; }

/* ============ Typographie ============ */
h1, h2, h3, h4, h5 {
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 700 !important;
    color: __TEXTE__ !important;
    letter-spacing: -0.01em;
}
body, p, div, span, li, td, th, label, input, button { font-family: 'Inter', sans-serif; }
.ba-kpi-value, .ba-choice-value, div[data-testid="stDataFrame"], .ba-periode-resume {
    font-variant-numeric: tabular-nums;
    font-feature-settings: 'tnum' 1;
}

/* ============ Boutons d'action ============ */
/* Descendant (pas enfant direct) : un bouton avec `help=` est enveloppé par
   Streamlit dans un conteneur de tooltip supplémentaire, qui casse le
   sélecteur `>` et laissait le bouton natif (non doré) s'afficher — cas des
   cartes de choix de l'accueil. */
.stButton button, .stDownloadButton button, .stFormSubmitButton button {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 0.82rem;
    letter-spacing: 0.015em;
    background: linear-gradient(180deg, __GOLD_LIGHT__ 0%, __GOLD__ 45%, __GOLD_DARK__ 100%);
    color: __NAVY_DARKEST__;
    border: none;
    border-radius: 10px;
    padding: 0.6rem 1.2rem;
    width: 100%;
    box-shadow: 0 1px 0 rgba(255,255,255,0.28) inset, 0 8px 20px -10px rgba(188,158,110,0.75);
    transition: transform .12s ease, box-shadow .16s ease, filter .16s ease;
}
.stButton button:hover, .stDownloadButton button:hover, .stFormSubmitButton button:hover {
    filter: brightness(1.07);
    transform: translateY(-1px);
    color: __NAVY_DARKEST__;
}
.stButton button:active { transform: translateY(0); }
.stButton button:focus, .stDownloadButton button:focus { color: __NAVY_DARKEST__; }
.stButton button:disabled, .stButton button:disabled:hover {
    background: rgba(255,255,255,0.045);
    color: rgba(159,179,194,0.55);
    box-shadow: inset 0 0 0 1px rgba(159,179,194,0.14);
    transform: none; filter: none; cursor: not-allowed;
}

/* ---- Navigation du module : boutons déguisés en entrées de menu ---- */
/* Entrée inactive */
.stButton > button[kind="tertiary"] {
    background: transparent !important;
    color: __TEXTE_ATTENUE__ !important;
    border: 1px solid transparent !important;
    border-left: 2px solid transparent !important;
    border-radius: 9px !important;
    box-shadow: none !important;
    text-align: left !important;
    justify-content: flex-start !important;
    font-weight: 500 !important;
    font-size: 0.86rem !important;
    letter-spacing: 0.01em !important;
    padding: 0.62rem 0.9rem !important;
    transform: none !important;
}
.stButton > button[kind="tertiary"]:hover {
    background: rgba(188,158,110,0.09) !important;
    color: __TEXTE__ !important;
    transform: none !important;
}
/* Entrée active */
.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, rgba(188,158,110,0.22), rgba(188,158,110,0.06)) !important;
    color: #FFF1DC !important;
    border: none !important;
    border-left: 2px solid __GOLD__ !important;
    border-radius: 9px !important;
    box-shadow: none !important;
    text-align: left !important;
    justify-content: flex-start !important;
    font-weight: 600 !important;
    font-size: 0.86rem !important;
    padding: 0.62rem 0.9rem !important;
    transform: none !important;
}
.stButton > button[kind="primary"]:hover {
    filter: brightness(1.08); transform: none !important; color: #FFF1DC !important;
}

/* ============ Champs et listes ============ */
.stTextInput input, .stNumberInput input, .stDateInput input {
    background-color: rgba(255,255,255,0.045) !important;
    color: __TEXTE__ !important;
    border: 1px solid rgba(188,158,110,0.22) !important;
    border-radius: 10px !important;
    padding: 0.7rem 0.85rem !important;
}
.stTextInput input:focus {
    border-color: rgba(188,158,110,0.62) !important;
    box-shadow: 0 0 0 3px rgba(188,158,110,0.14) !important;
}
div[data-baseweb="select"] > div {
    background-color: rgba(255,255,255,0.045) !important;
    border: 1px solid rgba(188,158,110,0.22) !important;
    border-radius: 10px !important;
    color: __TEXTE__ !important;
    min-height: 42px;
}
div[data-baseweb="select"] > div:hover { border-color: rgba(188,158,110,0.45) !important; }
div[data-baseweb="popover"] div[role="listbox"] {
    background: #0A2B40;
    border: 1px solid rgba(188,158,110,0.25);
    border-radius: 12px;
    box-shadow: 0 24px 60px -18px rgba(0,0,0,0.8);
}
div[data-baseweb="popover"] li:hover { background: rgba(188,158,110,0.14) !important; }
span[data-baseweb="tag"] {
    background: rgba(188,158,110,0.18) !important;
    border: 1px solid rgba(188,158,110,0.35) !important;
    color: __TEXTE__ !important;
    border-radius: 7px !important;
}

div[data-testid="stWidgetLabel"] label, div[data-testid="stWidgetLabel"] p {
    color: __TEXTE_ATTENUE__ !important;
    font-size: 0.66rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.13em !important;
    text-transform: uppercase !important;
    margin-bottom: 0.3rem !important;
}

/* ============ Bandeau de filtres : une seule ligne de base ============ */
/* Les trois contrôles n'ont pas la même anatomie (liste déroulante contre
   contrôle segmenté) : sans hauteur d'étiquette commune, leurs champs se
   décalaient verticalement. */
div[data-testid="stWidgetLabel"] { min-height: 1.15rem; }
div[data-testid="stSegmentedControl"] { margin-top: 0 !important; }
.ba-periode-resume { margin-top: .55rem; }

/* ============ Sélecteur segmenté (raccourcis de période) ============ */
div[data-testid="stSegmentedControl"] > div,
div[data-testid="stSegmentedControl"] [role="radiogroup"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(188,158,110,0.20);
    border-radius: 10px;
    padding: 3px;
    gap: 2px;
}
div[data-testid="stSegmentedControl"] button {
    background: transparent !important;
    border: none !important;
    border-radius: 7px !important;
    color: __TEXTE_ATTENUE__ !important;
    font-size: 0.74rem !important;
    font-weight: 600 !important;
    padding: 0.34rem 0.7rem !important;
    white-space: nowrap !important;
    box-shadow: none !important;
}
div[data-testid="stSegmentedControl"] button:hover {
    background: rgba(188,158,110,0.10) !important; color: __TEXTE__ !important;
}
div[data-testid="stSegmentedControl"] button[aria-checked="true"],
div[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
    background: linear-gradient(180deg, rgba(188,158,110,0.32), rgba(188,158,110,0.18)) !important;
    color: #FFF3DF !important;
    box-shadow: 0 1px 0 rgba(255,255,255,0.16) inset !important;
}

/* ============ Panneaux rétractables ============ */
div[data-testid="stExpander"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.018));
    border: 1px solid rgba(188,158,110,0.18);
    border-radius: 13px;
    box-shadow: 0 1px 0 rgba(255,255,255,0.05) inset, 0 14px 34px -22px rgba(0,0,0,0.85);
    margin-bottom: 0.7rem;
    overflow: hidden;
}
div[data-testid="stExpander"] summary {
    color: __TEXTE_ATTENUE__ !important;
    font-weight: 600;
    font-size: 0.74rem;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    padding: 0.72rem 1rem;
}
div[data-testid="stExpander"] summary:hover { color: __GOLD_LIGHT__ !important; }

/* ============ Tableaux et alertes ============ */
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(188,158,110,0.16);
    border-radius: 12px;
    overflow: hidden;
}
div[data-testid="stAlert"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(188,158,110,0.22);
    border-radius: 12px;
    color: __TEXTE__;
}

/* ======================================================================== */
/* COMPOSANTS DE LA CHARTE                                                  */
/* ======================================================================== */

.ba-card {
    background: linear-gradient(180deg, rgba(255,255,255,0.055) 0%, rgba(255,255,255,0.016) 100%);
    border: 1px solid rgba(188,158,110,0.20);
    border-top-color: rgba(188,158,110,0.42);
    border-radius: 18px;
    box-shadow: 0 1px 0 rgba(255,255,255,0.07) inset, 0 28px 60px -30px rgba(0,0,0,0.92);
    padding: 1.9rem 2.1rem;
}

/* -- Bandeau supérieur : logo à gauche, compte à droite -- */
.ba-topbar-rule {
    height: 1px; border: 0; margin: 0.9rem 0 1.6rem 0;
    background: linear-gradient(90deg,
        rgba(188,158,110,0.55) 0%, rgba(188,158,110,0.16) 45%, rgba(188,158,110,0.03) 100%);
}
/* Le logo suit la largeur de sa colonne via use_container_width : sans
   plafond en pixels fixes, il grossit démesurément sur les écrans larges.
   Une hauteur maximale stable garantit un rendu identique quelle que soit
   la largeur de la colonne. */
.st-key-ba_logo_bandeau [data-testid="stImage"],
.st-key-ba_logo_bandeau [data-testid="stImageContainer"] {
    display: flex !important;
    width: auto !important;
}
.st-key-ba_logo_bandeau [data-testid="stImage"] img,
.st-key-ba_logo_bandeau [data-testid="stImageContainer"] img {
    max-height: 60px !important;
    width: auto !important;
    display: block !important;
}
/* Le nom, la pastille et le bouton partagent un conteneur horizontal
   natif ; ce bloc ne porte donc plus aucune marge d'ajustement. */
.st-key-ba_compte_barre { align-items: center !important; }
/* Chaque enfant du conteneur porte, par défaut, une marge basse (héritée du
   rythme vertical normal de Streamlit) qui n'a pas lieu d'être ici : elle
   décale son centrage flex et le bouton paraît surélevé par rapport au bloc
   nom/pastille. On l'annule pour que les deux enfants se centrent sur leur
   seul contenu. */
.st-key-ba_compte_barre div[data-testid="stElementContainer"] {
    margin: 0 !important;
    align-self: center !important;
}
.st-key-ba_compte_barre .stButton { margin: 0 !important; }
.st-key-ba_compte_barre .stButton > button { width: auto !important; }
.ba-compte {
    display: flex; align-items: center; justify-content: flex-end;
    gap: 0.6rem;
}
.ba-compte-icone {
    width: 34px; height: 34px; border-radius: 50%;
    background: rgba(188,158,110,0.13);
    border: 1px solid rgba(188,158,110,0.38);
    display: flex; align-items: center; justify-content: center; flex: none;
}
.ba-compte-bloc { text-align: right; line-height: 1.25; }
.ba-compte-role {
    font-size: 0.58rem; font-weight: 600; letter-spacing: 0.16em;
    text-transform: uppercase; color: __TEXTE_ATTENUE__;
}
.ba-compte-nom {
    font-size: 0.87rem; font-weight: 600; color: __TEXTE__;
}

/* -- En-tête de page -- */
.ba-page-title {
    font-family: 'Montserrat', sans-serif;
    font-weight: 700; font-size: 1.72rem; color: __TEXTE__;
    margin: 0; line-height: 1.15; letter-spacing: -0.015em;
}
.ba-page-sub {
    font-size: 0.87rem; color: __TEXTE_ATTENUE__;
    margin-top: 0.4rem; max-width: 74ch; line-height: 1.6;
}

.ba-divider {
    height: 1px; border: 0;
    background: linear-gradient(90deg,
        rgba(188,158,110,0.62) 0%, rgba(188,158,110,0.18) 35%, rgba(188,158,110,0.03) 100%);
    margin: 1.3rem 0 1.8rem 0;
}

/* -- Titre de section -- */
.ba-section { display: flex; align-items: center; gap: 0.7rem; margin: 1.9rem 0 0.9rem 0; }
.ba-section-bar {
    width: 2px; height: 17px; border-radius: 2px; flex: none;
    background: linear-gradient(180deg, __GOLD_LIGHT__, rgba(188,158,110,0.15));
}
.ba-section-text {
    font-family: 'Montserrat', sans-serif; font-weight: 600; font-size: 0.78rem;
    color: __TEXTE__; letter-spacing: 0.15em; text-transform: uppercase;
}

/* -- Panneau de navigation du module -- */
/* Le conteneur natif porte la clé "ba_nav" : Streamlit la publie en classe
   .st-key-ba_nav, seul moyen fiable de styler un bloc qui contient des
   widgets (un <div> injecté ne peut pas les envelopper). */
/* Titre de section : il domine nettement les entrées de menu, sans quoi
   la colonne se lisait comme une liste plate sans en-tête. */
.ba-nav-titre {
    font-family: 'Montserrat', sans-serif;
    font-weight: 700;
    font-size: 1.02rem;
    line-height: 1.2;
    letter-spacing: 0.02em;
    color: __TEXTE__;
    margin: 0 0 0.55rem 0.15rem;
}
.ba-nav-filet {
    width: 34px; height: 2px; border-radius: 2px;
    margin: 0 0 1.1rem 0.15rem;
    background: linear-gradient(90deg, __GOLD__, rgba(188,158,110,0.12));
}
.st-key-ba_nav {
    background: linear-gradient(180deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.012) 65%, rgba(8,40,61,0.10) 100%);
    border: 1px solid rgba(188,158,110,0.16);
    border-top: 1px solid rgba(188,158,110,0.40);
    border-radius: 14px;
    box-shadow: 0 1px 0 rgba(255,255,255,0.06) inset, 0 22px 48px -32px rgba(0,0,0,0.92);
    padding: 1.15rem 0.85rem;
    gap: 0.12rem;
}
/* Les entrées de menu se suivent : aucun interligne parasite. */
.st-key-ba_nav div[data-testid="stElementContainer"] { margin-bottom: 0 !important; }

/* Entrées de menu : plus d'air, icône détachée du libellé. */
.st-key-ba_nav .stButton > button {
    padding: 0.62rem 0.75rem !important;
    margin: 0.09rem 0 !important;
    font-size: 0.84rem !important;
    letter-spacing: 0.005em !important;
    gap: 0.62rem !important;
    border-radius: 9px !important;
}
.st-key-ba_nav .stButton > button [data-testid="stIconMaterial"],
.st-key-ba_nav .stButton > button span[class*="material"] {
    font-size: 17px !important;
    opacity: .82;
}
.st-key-ba_nav .stButton > button[kind="primary"] [data-testid="stIconMaterial"] {
    opacity: 1;
    color: __GOLD_LIGHT__ !important;
}

/* -- Carte d'indicateur clé -- */
.ba-kpi {
    position: relative;
    background: linear-gradient(180deg, rgba(255,255,255,0.055) 0%, rgba(255,255,255,0.015) 100%);
    border: 1px solid rgba(188,158,110,0.18);
    border-top-color: rgba(188,158,110,0.40);
    border-radius: 15px;
    box-shadow: 0 1px 0 rgba(255,255,255,0.07) inset, 0 22px 46px -30px rgba(0,0,0,0.92);
    padding: 1.1rem 1.3rem 1rem 1.3rem;
    margin-bottom: 0.8rem;
    overflow: hidden;
}
.ba-kpi::before {
    content: ''; position: absolute; left: 0; top: 14%; bottom: 14%; width: 2px;
    background: linear-gradient(180deg, rgba(188,158,110,0), __GOLD__, rgba(188,158,110,0));
}
.ba-kpi-label {
    font-size: 0.63rem; font-weight: 600; letter-spacing: 0.16em;
    text-transform: uppercase; color: __TEXTE_ATTENUE__;
}
.ba-kpi-value {
    font-size: 2.3rem; font-weight: 700; color: __GOLD__;
    line-height: 1.05; margin-top: 0.32rem; letter-spacing: -0.02em;
}
.ba-kpi-unit {
    font-size: 1.05rem; font-weight: 500; color: rgba(188,158,110,0.62); margin-left: 0.1rem;
}
.ba-kpi-delta {
    display: inline-flex; align-items: center; gap: 0.3rem;
    font-size: 0.75rem; font-weight: 600; margin-top: 0.55rem;
    padding: 0.2rem 0.55rem; border-radius: 999px; line-height: 1.5;
}
.ba-kpi-delta-note {
    display: block; font-weight: 400; color: __TEXTE_ATTENUE__;
    font-size: 0.67rem; margin-top: 0.4rem;
}

/* -- Cartes de choix de l'accueil -- */
.ba-choice {
    background: linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.016) 100%);
    border: 1px solid rgba(188,158,110,0.20);
    border-top-color: rgba(188,158,110,0.45);
    border-radius: 18px;
    box-shadow: 0 1px 0 rgba(255,255,255,0.07) inset, 0 30px 64px -32px rgba(0,0,0,0.92);
    padding: 2rem 2.1rem 1.7rem 2.1rem;
    min-height: 296px;
}
.ba-choice-muted { opacity: 0.42; }
.ba-choice-eyebrow {
    font-size: 0.63rem; font-weight: 600; letter-spacing: 0.16em;
    text-transform: uppercase; color: __TEXTE_ATTENUE__;
}
.ba-choice-title {
    font-family: 'Montserrat', sans-serif; font-weight: 700; font-size: 1.3rem;
    color: __TEXTE__; margin: 0.4rem 0 0.9rem 0;
}
.ba-choice-value {
    font-size: 2.65rem; font-weight: 700; color: __GOLD__;
    line-height: 1.05; letter-spacing: -0.02em;
}
.ba-choice-desc {
    font-size: 0.85rem; color: __TEXTE_ATTENUE__; line-height: 1.7; margin-top: 0.85rem;
}
.ba-choice-tags {
    display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 1.1rem;
}
.ba-choice-tag {
    font-size: 0.66rem; font-weight: 600; letter-spacing: 0.03em;
    color: __TEXTE_ATTENUE__; background: rgba(255,255,255,0.035);
    border: 1px solid rgba(188,158,110,0.22); border-radius: 999px;
    padding: 0.28rem 0.7rem; white-space: nowrap;
}

/* -- Résumé de la période sélectionnée -- */
.ba-periode-resume {
    display: inline-flex; align-items: center; gap: 0.45rem;
    font-size: 0.76rem; font-weight: 600; color: __TEXTE__;
    background: rgba(255,255,255,0.035);
    border: 1px solid rgba(188,158,110,0.18);
    border-radius: 999px; padding: 0.26rem 0.85rem;
}
.ba-periode-fleche { color: __GOLD__; font-weight: 700; }
.ba-periode-compte {
    color: __TEXTE_ATTENUE__; font-weight: 400; font-size: 0.7rem;
    border-left: 1px solid rgba(188,158,110,0.22);
    padding-left: 0.55rem; margin-left: 0.1rem;
}

/* -- Badges (page de connexion) -- */
.ba-badge {
    display: inline-flex; align-items: center; gap: 0.45rem;
    font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em;
    padding: 0.42rem 1rem; border-radius: 999px; text-decoration: none;
}
.ba-badge-or {
    background: rgba(188,158,110,0.16);
    border: 1px solid rgba(188,158,110,0.45);
    color: __GOLD_LIGHT__;
}
.ba-badge-cyan {
    background: rgba(26,166,209,0.14);
    border: 1px solid rgba(26,166,209,0.48);
    color: #5CC8E8;
}
.ba-badge-cyan:hover {
    background: rgba(26,166,209,0.24);
    border-color: #1AA6D1;
    color: #8BDCF3;
}

/* =====================================================================
   RESPONSIVE — le contenu s'adapte, l'utilisateur ne zoome pas
   ===================================================================== */

/* Écrans très larges (2560 et plus) : on gagne un peu de corps de texte
   plutôt que d'étirer indéfiniment les colonnes. */
@media (min-width: 2000px) {
    html { font-size: 17px; }
    div.block-container { max-width: 1780px; }
}

/* Ordinateurs portables standards (1366-1600) */
@media (max-width: 1600px) {
    .ba-page-title { font-size: 1.55rem; }
    .ba-kpi-value { font-size: 2rem; }
    .st-key-ba_nav { padding: 0.9rem 0.65rem; }
    .st-key-ba_nav .stButton > button {
        font-size: 0.79rem !important;
        padding: 0.55rem 0.6rem !important;
        gap: 0.5rem !important;
    }
    .ba-nav-titre { font-size: 0.94rem; }
}

/* Écrans étroits : la navigation passe en bandeau, les colonnes s'empilent
   d'elles-mêmes (comportement natif de Streamlit sous ~640px par colonne). */
@media (max-width: 1100px) {
    div.block-container { padding-left: 1rem; padding-right: 1rem; }
    .ba-page-title { font-size: 1.35rem; }
    .ba-page-sub { font-size: 0.82rem; }
    .st-key-ba_nav {
        border: 1px solid rgba(188,158,110,0.16);
        border-top: 1px solid rgba(188,158,110,0.40);
        border-radius: 12px;
        padding: 0.8rem 0.7rem;
        margin-bottom: 0.8rem;
    }
    .ba-kpi-value { font-size: 1.75rem; }
    .ba-compte-role { display: none; }
}

/* -- Pied de page : blanc, lisible -- */
.ba-footer {
    text-align: center;
    color: __TEXTE__;
    font-size: 0.74rem;
    font-weight: 500;
    line-height: 1.8;
    margin-top: 3rem;
    padding-top: 1.4rem;
    border-top: 1px solid rgba(188,158,110,0.14);
}
</style>
"""

for _jeton, _valeur in [
    ("__NAVY_DARKEST__", NAVY_DARKEST),
    ("__NAVY_DEEP__", NAVY_DEEP),
    ("__NAVY_LIGHT__", NAVY_LIGHT),
    ("__GOLD_LIGHT__", GOLD_LIGHT),
    ("__GOLD_DARK__", GOLD_DARK),
    ("__GOLD__", GOLD),
    ("__TEXTE_ATTENUE__", TEXTE_ATTENUE),
    ("__TEXTE__", TEXTE),
    ("__CARTE_BORDURE__", CARTE_BORDURE),
    ("__CARTE_FOND__", CARTE_FOND),
]:
    _CSS = _CSS.replace(_jeton, _valeur)


def appliquer_theme():
    """Injecte la charte. À appeler une fois par page, après configurer_page()."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 5. Briques de mise en page
# ---------------------------------------------------------------------------


def entete_page(titre, sous_titre=""):
    """Titre de page. Le nom de l'institution n'est PAS répété ici : il est
    porté en permanence par le logo du bandeau supérieur."""
    bloc = "<div class='ba-page-title'>" + titre + "</div>"
    if sous_titre:
        bloc += "<div class='ba-page-sub'>" + sous_titre + "</div>"
    st.markdown(bloc, unsafe_allow_html=True)


def separateur_dore():
    st.markdown("<hr class='ba-divider'/>", unsafe_allow_html=True)


def titre_section(texte):
    st.markdown(
        "<div class='ba-section'><div class='ba-section-bar'></div>"
        "<div class='ba-section-text'>" + texte + "</div></div>",
        unsafe_allow_html=True,
    )


def pied_de_page():
    from datetime import datetime

    st.markdown(
        "<div class='ba-footer'>&copy; "
        + str(datetime.now().year)
        + " "
        + INSTITUTION
        + " — Tous droits réservés.<br/>Accès réservé au personnel autorisé.</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# 6. Habillage des graphiques
# ---------------------------------------------------------------------------

# Séries totalisantes : elles ne consomment pas d'emplacement de palette.
# « Contribution Core » / « Contribution Non-Core » en sont exclus : dans le
# graphique core/non-core, ce sont les deux catégories comparées.
_AGREGATS_EXACTS = {
    "IPC (%)",
    "IPC Core (%)",
    "IPC Non Core (%)",
    "Inflation (%, mom)",
    "Inflation (%, yoy)",
}


def _est_agregat(nom):
    if not isinstance(nom, str):
        return False
    nom = nom.strip()
    return nom.startswith("Inflation IPC") or nom in _AGREGATS_EXACTS


def _titre_existant(fig):
    """Texte du titre déjà porté par la figure, ou None."""
    titre = getattr(fig.layout, "title", None)
    if titre is None:
        return None
    texte = getattr(titre, "text", None)
    if texte is None or str(texte).strip() in ("", "undefined", "None"):
        return None
    return str(texte)


def appliquer_theme_graphique(fig, hauteur=None, titre=None):
    """
    Aligne une figure Plotly sur la charte : fond transparent, police Inter,
    grille discrète, survol unifié et palette de séries validée.

    `titre` remplace le titre porté par la figure. Sans titre ni existant ni
    fourni, le titre est vidé explicitement (title=None produirait le texte
    « undefined » à l'écran).
    """
    if fig is None:
        return None

    emplacement = 0
    for trace in fig.data:
        # Couleurs fixées par le tracé (contours de carte en or, etc.) : on n'y touche pas.
        if getattr(trace, "meta", None) == "couleur_fixe":
            continue
        # Une courbe déjà tracée à l'encre du texte est un total (PIB total,
        # croissance du PIB) : même traitement que les agrégats nommés.
        total_trace = trace.type == "scatter" and getattr(trace.line, "color", None) == TEXTE
        if _est_agregat(getattr(trace, "name", None)) or total_trace:
            if trace.type == "scatter":
                trace.line.color = COULEUR_AGREGAT
                trace.line.width = 2.4
                if trace.mode and "markers" in trace.mode:
                    trace.marker.color = COULEUR_AGREGAT
                    trace.marker.size = 4
            continue

        couleur = PALETTE_SERIES[emplacement % len(PALETTE_SERIES)]
        emplacement += 1

        if trace.type == "bar":
            # Une couleur posée BARRE PAR BARRE porte du sens (signe d'une
            # contribution, alerte…) : l'écraser par un emplacement de palette
            # effacerait l'information. On ne recolore que les séries unies.
            couleur_posee = trace.marker.color
            if not isinstance(couleur_posee, (list, tuple)):
                trace.marker.color = couleur
            trace.marker.line.color = NAVY_DEEP
            trace.marker.line.width = 1
        elif trace.type == "scatter":
            trace.line.color = couleur
            trace.line.width = 1.9
            if trace.mode and "markers" in trace.mode:
                trace.marker.color = couleur
                trace.marker.size = 4
        elif trace.type == "pie":
            trace.marker.colors = [GOLD, CYAN_LIGHT]

    # Les barres empilées portaient une étiquette pivotée par segment : sur
    # soixante mois et huit postes, cela fait quatre cents libellés illisibles
    # par-dessus le graphique. Le survol et le tableau donnent déjà la valeur.
    barres = [t for t in fig.data if t.type == "bar"]
    if len(barres) > 2 and getattr(fig.layout, "barmode", None) in ("relative", "stack"):
        for trace in barres:
            trace.text = None
            trace.texttemplate = None

    texte_titre = titre if titre is not None else _titre_existant(fig)
    marge_haute = 96 if texte_titre else 64

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=12, color=TEXTE_ATTENUE),
        legend=dict(
            orientation="h",
            y=1.0,
            x=0,
            xanchor="left",
            yanchor="bottom",
            font=dict(family="Inter, sans-serif", size=11, color=TEXTE_ATTENUE),
            bgcolor="rgba(0,0,0,0)",
            title="",
        ),
        hoverlabel=dict(
            bgcolor=NAVY_DARKEST,
            bordercolor=GOLD_DARK,
            font=dict(family="Inter, sans-serif", size=12, color=TEXTE),
        ),
        margin=dict(l=8, r=14, t=marge_haute, b=8),
        bargap=0.2,
    )

    if texte_titre:
        fig.update_layout(
            title=dict(
                text=texte_titre,
                font=dict(family="Montserrat, sans-serif", size=15, color=TEXTE),
                x=0,
                xanchor="left",
                y=0.98,
                yanchor="top",
            )
        )
    else:
        fig.update_layout(title_text="")

    if hauteur:
        fig.update_layout(height=hauteur)

    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor="rgba(159,179,194,0.18)",
        tickfont=dict(family="Inter, sans-serif", size=11, color=TEXTE_ATTENUE),
        title_font=dict(family="Inter, sans-serif", size=11, color=TEXTE_ATTENUE),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=GRILLE,
        gridwidth=1,
        zeroline=True,
        zerolinecolor="rgba(159,179,194,0.26)",
        zerolinewidth=1,
        linecolor="rgba(0,0,0,0)",
        tickfont=dict(family="Inter, sans-serif", size=11, color=TEXTE_ATTENUE),
        title_font=dict(family="Inter, sans-serif", size=11, color=TEXTE_ATTENUE),
    )

    for forme in fig.layout.shapes or []:
        if getattr(forme, "line", None) is not None:
            forme.line.color = GOLD
            forme.line.width = 1.1
    for annot in fig.layout.annotations or []:
        annot.font.family = "Inter, sans-serif"
        # Un titre de sous-graphique est ancré sur le papier ; une annotation
        # de repère (« Cible 4 % ») est ancrée sur les données.
        titre_de_panneau = getattr(annot, "xref", None) == "paper" and getattr(annot, "yref", None) == "paper"
        if titre_de_panneau:
            annot.font.color = TEXTE_ATTENUE
            annot.font.size = 12
        else:
            annot.font.color = GOLD
            annot.font.size = 11

    return fig
