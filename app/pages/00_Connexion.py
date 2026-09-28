"""
Page de connexion — Dashboard économique de la Banque d'Algérie.

Refonte UI :
- écran institutionnel plein écran ;
- panneau gauche éditorial et visuel ;
- panneau droit dédié à l'authentification ;
- carte de connexion élégante ;
- aucune balise HTML ouverte autour de widgets Streamlit ;
- responsive desktop / tablette / mobile.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from config.settings import USERS_FILE, LOGO_PATH
from app.components.theme import configurer_page, appliquer_theme, INSTITUTION, SITE_OFFICIEL


# =============================================================================
# UTILITAIRE — évite que Markdown ne confonde du HTML indenté avec un bloc
# de code (règle CommonMark : 4 espaces d'indentation = bloc de code affiché
# tel quel, sans jamais être interprété comme du HTML, même avec
# unsafe_allow_html=True). On retire donc l'indentation de chaque ligne tout
# en gardant le code source lisible.
# =============================================================================

def html_block(texte: str) -> str:
    return "\n".join(ligne.lstrip() for ligne in texte.strip("\n").splitlines())


# =============================================================================
# CONFIGURATION
# =============================================================================

configurer_page("Connexion")
appliquer_theme()


# =============================================================================
# CSS
# =============================================================================

st.markdown(
    html_block(
        """
        <style>

        /* =====================================================================
           1. RESET GLOBAL STREAMLIT
           ===================================================================== */

        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stApp"] {
            background: #06182A !important;
        }

        [data-testid="stHeader"] {
            background: transparent !important;
        }

        [data-testid="stToolbar"] {
            display: none !important;
        }

        [data-testid="stDecoration"] {
            display: none !important;
        }

        .block-container {
            max-width: 100% !important;
            width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
        }

        [data-testid="stMainBlockContainer"] {
            padding: 0 !important;
            margin: 0 !important;
        }

        [data-testid="stMain"] {
            padding: 0 !important;
            margin: 0 !important;
        }

        /* =====================================================================
           2. STRUCTURE PRINCIPALE
           ===================================================================== */

        [data-testid="stHorizontalBlock"] {
            width: 100% !important;
            max-width: 100% !important;
            min-height: calc(100vh - 58px) !important;
            margin: 0 !important;
            padding: 0 !important;
            gap: 0 !important;
            align-items: stretch !important;
        }

        [data-testid="column"] {
            margin: 0 !important;
            padding: 0 !important;
        }

        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            min-height: calc(100vh - 58px) !important;
        }

        /* =====================================================================
           3. PANNEAU GAUCHE
           ===================================================================== */

        [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child {
            position: relative !important;
            overflow: hidden !important;
            flex: 1.08 1 0 !important;
            background:
                radial-gradient(circle at 25% 32%, rgba(28,77,113,.28) 0%, rgba(28,77,113,.10) 32%, transparent 65%),
                linear-gradient(145deg, #06182A 0%, #08213A 48%, #06182A 100%) !important;
            border-right: 1px solid rgba(215,169,67,.20) !important;
        }

        [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child::before {
            content: "";
            position: absolute;
            inset: 0;
            background-image: radial-gradient(circle, rgba(91,137,170,.30) 1px, transparent 1.6px);
            background-size: 12px 12px;
            -webkit-mask-image: radial-gradient(ellipse at 32% 30%, black 0%, rgba(0,0,0,.85) 28%, transparent 67%);
            mask-image: radial-gradient(ellipse at 32% 30%, black 0%, rgba(0,0,0,.85) 28%, transparent 67%);
            opacity: .40;
            pointer-events: none;
            z-index: 0;
        }

        [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child::after {
            content: "";
            position: absolute;
            width: 720px;
            height: 720px;
            left: -260px;
            top: -220px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(24,75,113,.20) 0%, rgba(24,75,113,.07) 42%, transparent 72%);
            pointer-events: none;
            z-index: 0;
        }

        /* =====================================================================
           4. HERO
           ===================================================================== */

        .ba-hero {
            position: relative;
            z-index: 5;
            min-height: calc(100vh - 58px);
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 4rem clamp(3rem, 5.5vw, 6.8rem) 5rem clamp(3.5rem, 6vw, 7.5rem);
            overflow: hidden;
        }

        .ba-hero-content {
            position: relative;
            z-index: 10;
            width: min(560px, 90%);
            margin-top: 2rem;
        }

        .ba-eyebrow {
            width: 78px;
            height: 3px;
            margin-bottom: 1.65rem;
            background: linear-gradient(90deg, #D7A943, #E5BD67);
            border-radius: 10px;
            box-shadow: 0 0 18px rgba(215,169,67,.12);
        }

        .ba-hero-title {
            margin: 0;
            color: #F4F6F8;
            font-family: "Montserrat", "Segoe UI", Arial, sans-serif;
            font-size: clamp(2.35rem, 3.55vw, 4rem);
            font-weight: 750;
            line-height: 1.07;
            letter-spacing: -.035em;
        }

        .ba-hero-title span { display: block; }

        .ba-hero-subtitle {
            max-width: 520px;
            margin-top: 1.45rem;
            color: #AEBECD;
            font-family: "Montserrat", "Segoe UI", Arial, sans-serif;
            font-size: clamp(.98rem, 1.12vw, 1.14rem);
            font-weight: 400;
            line-height: 1.65;
        }

        /* =====================================================================
           5. FEATURES
           ===================================================================== */

        .ba-hero-features {
            display: grid;
            grid-template-columns: repeat(4, minmax(80px, 1fr));
            max-width: 610px;
            gap: 2rem;
            margin-top: 3.1rem;
        }

        .ba-feature { min-width: 0; }

        .ba-feature-icon {
            width: 34px;
            height: 34px;
            margin-bottom: .75rem;
            color: #D7A943;
        }

        .ba-feature-icon svg { width: 100%; height: 100%; }

        .ba-feature-label {
            color: #B9C7D3;
            font-family: "Montserrat", "Segoe UI", Arial, sans-serif;
            font-size: .79rem;
            line-height: 1.38;
        }

        /* =====================================================================
           6. ÉLÉMENTS GRAPHIQUES GAUCHE
           ===================================================================== */

        .ba-world-map {
            position: absolute; z-index: 1;
            width: min(73%, 760px); height: auto;
            top: 3%; left: -7%;
            opacity: .42; pointer-events: none;
        }

        .ba-chart {
            position: absolute; z-index: 2;
            width: min(61%, 610px); height: auto;
            top: 15%; right: -1%;
            opacity: .74; pointer-events: none;
        }

        .ba-building {
            position: absolute; z-index: 2;
            width: min(53%, 540px); height: auto;
            left: -3%; bottom: -5%;
            opacity: .20; pointer-events: none;
        }

        .ba-contour {
            position: absolute; z-index: 1;
            width: 82%; height: 62%;
            right: -16%; bottom: -25%;
            opacity: .20; pointer-events: none;
        }

        /* =====================================================================
           7. PANNEAU DROIT
           ===================================================================== */

        [data-testid="stHorizontalBlock"] > [data-testid="column"]:last-child {
            position: relative !important;
            overflow: hidden !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            flex: .92 1 0 !important;
            background:
                radial-gradient(circle at 50% 45%, rgba(18,54,84,.38) 0%, transparent 58%),
                #071A2D !important;
            padding: 4.5rem clamp(2.2rem, 4.2vw, 5rem) 3rem !important;
        }

        [data-testid="stHorizontalBlock"] > [data-testid="column"]:last-child::before {
            content: "";
            position: absolute;
            left: 0; top: 8%; bottom: 8%;
            width: 1px;
            background: linear-gradient(to bottom, transparent, rgba(207,162,72,.32), transparent);
            pointer-events: none;
        }

        /* =====================================================================
           8. BARRE SUPÉRIEURE
           ===================================================================== */

        .ba-topbar {
            position: absolute;
            z-index: 30;
            top: 1.7rem;
            right: clamp(2rem, 4vw, 4.5rem);
            display: flex;
            align-items: center;
            gap: 1.35rem;
            color: #B7C4D0;
            font-family: "Montserrat", "Segoe UI", Arial, sans-serif;
            font-size: .82rem;
        }

        .ba-help,
        .ba-help:visited {
            color: #C6D0D9;
            text-decoration: underline;
            text-decoration-style: dotted;
            text-underline-offset: 6px;
            transition: color .16s ease;
        }

        .ba-help:hover { color: #D7A943; }

        .ba-top-divider { width: 1px; height: 22px; background: rgba(255,255,255,.15); }

        .ba-language { display: flex; gap: 1.1rem; }
        .ba-language span { cursor: default; }
        .ba-language .active { color: #D7A943; font-weight: 700; }

        /* =====================================================================
           9. CARTE DE CONNEXION
           ===================================================================== */

        .st-key-ba_login_card {
            position: relative !important;
            z-index: 10 !important;
            width: min(100%, 640px) !important;
            box-sizing: border-box !important;
            padding: 3.4rem clamp(2.2rem, 3.5vw, 3.8rem) 2.65rem !important;
            margin: 1.8rem auto 0 auto !important;
            background: linear-gradient(145deg, rgba(16,42,65,.94), rgba(7,26,45,.94)) !important;
            border: 1px solid rgba(129,159,181,.27) !important;
            border-radius: 18px !important;
            box-shadow: 0 28px 80px rgba(0,0,0,.30), inset 0 1px 0 rgba(255,255,255,.045) !important;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }

        .st-key-ba_login_card::before {
            content: "";
            position: absolute;
            top: -1px; left: 14%; right: 14%;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(215,169,67,.68), transparent);
        }

        /* =====================================================================
           10. LOGO
           ===================================================================== */

        /* Streamlit rend l'image dans un conteneur déjà flex (justify-content
           flex-start par défaut) : un simple text-align ne centre rien, un
           enfant flex n'y répond pas. On force donc explicitement le centrage
           flex — mais seulement sur le conteneur QUI CONTIENT L'IMAGE :
           un sélecteur trop large (tout .st-key-ba_login_card
           [data-testid="stElementContainer"]) touchait aussi les champs de
           saisie et le bouton, qui perdaient alors leur largeur 100 % par
           défaut (comportement bloc) au profit d'une taille flex réduite au
           contenu. */
        .st-key-ba_login_card div[data-testid="stElementContainer"]:has(> [data-testid="stImage"]),
        .st-key-ba_login_card [data-testid="stImage"],
        .st-key-ba_login_card [data-testid="stImageContainer"] {
            display: flex !important;
            justify-content: center !important;
            width: 100% !important;
        }

        .st-key-ba_login_card [data-testid="stImage"] img,
        .st-key-ba_login_card [data-testid="stImageContainer"] img {
            display: block !important;
            width: min(300px, 75%) !important;
            max-height: 115px !important;
            object-fit: contain !important;
            margin: 0 auto !important;
        }

        /* Le bouton « plein écran » que Streamlit superpose à toute image
           n'a pas de sens sur un logo institutionnel. */
        .st-key-ba_login_card [data-testid="stElementToolbar"],
        .st-key-ba_login_card [data-testid="StyledFullScreenButton"] {
            display: none !important;
        }

        /* =====================================================================
           11. EN-TÊTE DE LA CARTE
           ===================================================================== */

        .ba-login-rule {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: .55rem;
            margin: 1.35rem 0 1.35rem;
        }

        .ba-login-rule::before,
        .ba-login-rule::after {
            content: "";
            width: 54px;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(215,169,67,.78));
        }

        .ba-login-rule::after {
            background: linear-gradient(90deg, rgba(215,169,67,.78), transparent);
        }

        .ba-login-rule span {
            width: 5px; height: 5px;
            border-radius: 50%;
            background: #D7A943;
        }

        .ba-login-title {
            color: #F5F6F7;
            font-family: "Montserrat", "Segoe UI", Arial, sans-serif;
            font-size: clamp(1.55rem, 2vw, 2rem);
            font-weight: 700;
            line-height: 1.2;
            text-align: center;
        }

        .ba-login-sub {
            max-width: 430px;
            margin: .65rem auto 0;
            color: #9EB0BF;
            font-family: "Montserrat", "Segoe UI", Arial, sans-serif;
            font-size: .92rem;
            line-height: 1.55;
            text-align: center;
        }

        /* =====================================================================
           12. FORMULAIRE STREAMLIT
           ===================================================================== */

        .st-key-ba_login_form { margin-top: 2rem !important; width: 100% !important; }

        .st-key-ba_login_form [data-testid="stWidgetLabel"] p {
            color: #E2E7EB !important;
            font-family: "Montserrat", "Segoe UI", Arial, sans-serif !important;
            font-size: .86rem !important;
            font-weight: 650 !important;
        }

        .st-key-ba_login_form [data-testid="stTextInput"] { margin-bottom: .9rem !important; }

        .st-key-ba_login_form [data-testid="stTextInput"] > div {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }

        .st-key-ba_login_form input {
            box-sizing: border-box !important;
            min-height: 58px !important;
            width: 100% !important;
            background: rgba(2,15,28,.34) !important;
            border: 1px solid rgba(158,181,199,.38) !important;
            border-radius: 10px !important;
            color: #F1F4F6 !important;
            font-family: "Montserrat", "Segoe UI", Arial, sans-serif !important;
            font-size: .93rem !important;
            padding: .85rem 3rem .85rem 2.95rem !important;
            transition: border-color .18s ease, box-shadow .18s ease, background .18s ease !important;
        }

        .st-key-ba_login_form input::placeholder { color: #718598 !important; opacity: 1 !important; }

        .st-key-ba_login_form input:focus {
            background: rgba(4,22,38,.48) !important;
            border-color: #D2A64C !important;
            box-shadow: 0 0 0 1px rgba(210,166,76,.20), 0 0 22px rgba(210,166,76,.07) !important;
            outline: none !important;
        }

        /* Icône utilisateur — ciblage par clé du widget (fiable, pas de :nth-of-type) */
        .st-key-ba_login_form .st-key-login_username input {
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23D7A943' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='8' r='3.4'/%3E%3Cpath d='M5 20c0-3.7 3.1-6.5 7-6.5s7 2.8 7 6.5'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: 1rem center;
            background-size: 20px 20px;
        }

        /* Icône cadenas */
        .st-key-ba_login_form .st-key-login_password input {
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23D7A943' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='5' y='11' width='14' height='9' rx='2'/%3E%3Cpath d='M8 11V7a4 4 0 0 1 8 0v4'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: 1rem center;
            background-size: 20px 20px;
        }

        /* =====================================================================
           13. BOUTONS
           ===================================================================== */

        .st-key-ba_login_form .stButton { width: 100% !important; margin-top: .55rem !important; }

        .st-key-ba_login_form .st-key-btn_connexion button {
            position: relative !important;
            width: 100% !important;
            min-height: 58px !important;
            border-radius: 10px !important;
            border: 1px solid rgba(255,214,125,.36) !important;
            background:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2308192B' stroke-width='2.1' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M18.55 7.41A8 8 0 1 0 18.55 16.59'/%3E%3Cpath d='M2.2 12H15.3'/%3E%3Cpath d='M11.6 8.1L15.5 12L11.6 15.9'/%3E%3C/svg%3E")
                no-repeat right 1.35rem center / 23px 23px,
                linear-gradient(180deg, #E2B45B 0%, #C99532 100%) !important;
            color: #08192B !important;
            font-family: "Inter", "Segoe UI", Arial, sans-serif !important;
            font-size: 0.95rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.01em !important;
            padding-right: 3rem !important;
            box-shadow: 0 8px 22px rgba(0,0,0,.18), inset 0 1px 0 rgba(255,255,255,.24) !important;
            transition: transform .16s ease, filter .16s ease, box-shadow .16s ease !important;
        }

        .st-key-ba_login_form .st-key-btn_connexion button p {
            font-family: "Inter", "Segoe UI", Arial, sans-serif !important;
            font-size: 0.95rem !important;
            font-weight: 700 !important;
        }

        .st-key-ba_login_form .st-key-btn_connexion button:hover {
            filter: brightness(1.06) !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 12px 28px rgba(0,0,0,.24), 0 0 20px rgba(215,169,67,.08) !important;
        }

        .st-key-ba_login_form .st-key-mdp_oublie { margin-top: .45rem !important; }

        .st-key-ba_login_form .st-key-mdp_oublie button {
            width: auto !important;
            min-height: auto !important;
            margin: 0 auto !important;
            padding: .3rem .2rem .1rem !important;
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: #D7A943 !important;
            font-family: "Montserrat", "Segoe UI", Arial, sans-serif !important;
            font-size: .86rem !important;
            font-weight: 600 !important;
            text-decoration: underline !important;
            text-decoration-style: dotted !important;
            text-underline-offset: 5px;
        }

        .st-key-ba_login_form .st-key-mdp_oublie button:hover {
            color: #E7C778 !important;
            background: transparent !important;
        }

        /* =====================================================================
           14. ALERTES
           ===================================================================== */

        .st-key-ba_login_form [data-testid="stAlert"] {
            margin-top: .85rem !important;
            border-radius: 9px !important;
        }

        /* =====================================================================
           15. SÉCURITÉ
           ===================================================================== */

        .ba-security {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: .65rem;
            margin-top: 1.7rem;
            padding-top: 1.35rem;
            border-top: 1px solid rgba(255,255,255,.10);
            color: #9EAFBE;
            font-family: "Montserrat", "Segoe UI", Arial, sans-serif;
            font-size: .79rem;
            line-height: 1.4;
            text-align: center;
        }

        .ba-security svg { flex: 0 0 auto; width: 21px; height: 21px; }

        /* =====================================================================
           16. FOOTER
           ===================================================================== */

        .ba-footer {
            min-height: 58px;
            box-sizing: border-box;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: .85rem clamp(2rem, 4vw, 4.8rem);
            background: #06182A;
            border-top: 1px solid rgba(215,169,67,.38);
            color: #91A2B1;
            font-family: "Montserrat", "Segoe UI", Arial, sans-serif;
            font-size: .76rem;
        }

        .ba-footer-right { display: flex; align-items: center; gap: .55rem; white-space: nowrap; }
        .ba-footer-right svg { width: 16px; height: 16px; flex: 0 0 auto; }

        /* =====================================================================
           17. TABLETTE
           ===================================================================== */

        @media (max-width: 1050px) {
            .ba-hero { padding-left: 3rem; padding-right: 3rem; }
            .ba-hero-features { gap: 1.3rem; }
            .ba-hero-title { font-size: clamp(2rem, 4vw, 3rem); }
            .st-key-ba_login_card { padding-left: 2.2rem !important; padding-right: 2.2rem !important; }
        }

        /* =====================================================================
           18. MOBILE
           ===================================================================== */

        @media (max-width: 760px) {
            [data-testid="stHorizontalBlock"] { flex-direction: column !important; min-height: auto !important; }
            [data-testid="stHorizontalBlock"] > [data-testid="column"] { width: 100% !important; min-height: auto !important; }
            [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child { min-height: 470px !important; }
            .ba-hero { min-height: 470px; padding: 4.7rem 2rem 2.8rem; justify-content: flex-end; }
            .ba-hero-content { width: 100%; margin-top: 0; }
            .ba-hero-title { font-size: 2.25rem; }
            .ba-hero-subtitle { font-size: .92rem; }
            .ba-hero-features { gap: 1rem; margin-top: 2rem; }
            .ba-feature-label { font-size: .70rem; }
            .ba-world-map { width: 105%; top: -4%; left: -15%; }
            .ba-chart { width: 76%; top: 6%; right: -8%; }
            .ba-building { width: 70%; left: -8%; bottom: -10%; }
            [data-testid="stHorizontalBlock"] > [data-testid="column"]:last-child { min-height: auto !important; padding: 5.2rem 1.15rem 2rem !important; }
            .ba-topbar { top: 1.15rem; right: 1.15rem; }
            .st-key-ba_login_card { width: 100% !important; margin-top: 0 !important; padding: 2.3rem 1.25rem 1.9rem !important; border-radius: 15px !important; }
            .st-key-ba_login_card [data-testid="stImage"] { width: min(270px, 82%) !important; }
            .ba-footer { flex-direction: column; justify-content: center; text-align: center; }
            .ba-footer-right { white-space: normal; }
        }

        </style>
        """
    ),
    unsafe_allow_html=True,
)


# =============================================================================
# DONNÉES UTILISATEURS
# =============================================================================

def _bootstrap_utilisateurs():
    """
    Recrée `data/users.xlsx` à partir de `st.secrets["users"]` si le fichier a
    disparu — cas d'un système de fichiers non garanti persistant (Streamlit
    Community Cloud : redémarrage après inactivité). Les secrets, eux, sont
    conservés côté plateforme indépendamment du système de fichiers de
    l'application. Sans effet si le fichier existe déjà ou si aucun secret
    « users » n'est configuré (usage local / Docker avec volume monté).
    """
    if USERS_FILE.exists():
        return
    try:
        comptes = dict(st.secrets["users"])
    except Exception:
        comptes = {}
    if not comptes:
        return
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"username": list(comptes.keys()), "password": list(comptes.values())}).to_excel(
        USERS_FILE, index=False
    )


_bootstrap_utilisateurs()


@st.cache_data(show_spinner=False)
def charger_utilisateurs():
    return pd.read_excel(USERS_FILE)


utilisateurs = charger_utilisateurs()


# =============================================================================
# STRUCTURE PRINCIPALE
# =============================================================================

col_hero, col_form = st.columns([1.08, 0.92], gap="small")


# =============================================================================
# PANNEAU GAUCHE
# =============================================================================

with col_hero:
    st.markdown(
        html_block(
            f"""
            <div class="ba-hero">

                <svg class="ba-world-map" viewBox="0 0 760 360" xmlns="http://www.w3.org/2000/svg">
                    <g fill="#2E5A7D" opacity=".70">
                        <circle cx="80" cy="100" r="3"/>
                        <circle cx="100" cy="85" r="3"/>
                        <circle cx="120" cy="75" r="3"/>
                        <circle cx="140" cy="92" r="3"/>
                        <circle cx="158" cy="108" r="3"/>
                        <circle cx="180" cy="96" r="3"/>
                        <circle cx="200" cy="112" r="3"/>
                        <circle cx="218" cy="128" r="3"/>
                        <circle cx="310" cy="105" r="3"/>
                        <circle cx="330" cy="92" r="3"/>
                        <circle cx="350" cy="108" r="3"/>
                        <circle cx="372" cy="98" r="3"/>
                        <circle cx="394" cy="115" r="3"/>
                        <circle cx="416" cy="125" r="3"/>
                        <circle cx="438" cy="118" r="3"/>
                        <circle cx="460" cy="132" r="3"/>
                        <circle cx="505" cy="170" r="3"/>
                        <circle cx="530" cy="160" r="3"/>
                        <circle cx="555" cy="172" r="3"/>
                        <circle cx="580" cy="188" r="3"/>
                        <circle cx="605" cy="180" r="3"/>
                        <circle cx="630" cy="195" r="3"/>
                        <circle cx="235" cy="180" r="3"/>
                        <circle cx="250" cy="195" r="3"/>
                        <circle cx="265" cy="210" r="3"/>
                        <circle cx="280" cy="225" r="3"/>
                        <circle cx="295" cy="240" r="3"/>
                    </g>
                    <g fill="none" stroke="#315C7C" stroke-width="1" opacity=".35">
                        <path d="M25 85 C120 35, 200 55, 260 110 S420 150, 500 90 S650 70, 750 120"/>
                        <path d="M5 125 C100 75, 205 92, 280 145 S430 185, 530 125 S660 115, 760 160"/>
                        <path d="M0 165 C100 120, 210 135, 300 175 S455 220, 550 165 S670 160, 760 195"/>
                        <path d="M30 205 C120 165, 220 175, 315 205 S470 250, 565 205 S680 205, 755 230"/>
                    </g>
                </svg>

                <svg class="ba-chart" viewBox="0 0 610 340" xmlns="http://www.w3.org/2000/svg">
                    <g opacity=".42">
                        <rect x="52" y="220" width="30" height="75" rx="2" fill="#2C5575"/>
                        <rect x="120" y="190" width="30" height="105" rx="2" fill="#2C5575"/>
                        <rect x="188" y="158" width="30" height="137" rx="2" fill="#2C5575"/>
                        <rect x="256" y="130" width="30" height="165" rx="2" fill="#2C5575"/>
                        <rect x="324" y="98" width="30" height="197" rx="2" fill="#2C5575"/>
                        <rect x="392" y="62" width="30" height="233" rx="2" fill="#2C5575"/>
                        <rect x="460" y="35" width="30" height="260" rx="2" fill="#2C5575"/>
                    </g>
                    <path d="M67 225 L135 195 L203 160 L271 142 L339 105 L407 70 L475 42"
                          fill="none" stroke="#D7A943" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
                    <g fill="#D7A943">
                        <circle cx="67" cy="225" r="4"/>
                        <circle cx="135" cy="195" r="4"/>
                        <circle cx="203" cy="160" r="4"/>
                        <circle cx="271" cy="142" r="4"/>
                        <circle cx="339" cy="105" r="4"/>
                        <circle cx="407" cy="70" r="4"/>
                        <circle cx="475" cy="42" r="5"/>
                    </g>
                    <g fill="#B7C7D4" font-family="Montserrat, Segoe UI, Arial, sans-serif" font-size="14">
                        <text x="118" y="178">2,55</text>
                        <text x="186" y="143">3,35</text>
                        <text x="254" y="125">4,82</text>
                        <text x="397" y="52" fill="#F0F3F5" font-weight="700">6,17</text>
                    </g>
                </svg>

                <svg class="ba-building" viewBox="0 0 540 470" xmlns="http://www.w3.org/2000/svg"
                     fill="none" stroke="#66839C" stroke-width="1.2">
                    <polygon points="22,145 270,30 518,145"/>
                    <rect x="22" y="145" width="496" height="290"/>
                    <line x1="48" y1="145" x2="48" y2="435"/>
                    <line x1="108" y1="145" x2="108" y2="435"/>
                    <line x1="168" y1="145" x2="168" y2="435"/>
                    <line x1="228" y1="145" x2="228" y2="435"/>
                    <line x1="288" y1="145" x2="288" y2="435"/>
                    <line x1="348" y1="145" x2="348" y2="435"/>
                    <line x1="408" y1="145" x2="408" y2="435"/>
                    <line x1="468" y1="145" x2="468" y2="435"/>
                    <path d="M70 435 V270 Q78 245 86 270 V435"/>
                    <path d="M130 435 V270 Q138 245 146 270 V435"/>
                    <path d="M190 435 V270 Q198 245 206 270 V435"/>
                    <path d="M310 435 V270 Q318 245 326 270 V435"/>
                    <path d="M370 435 V270 Q378 245 386 270 V435"/>
                    <path d="M430 435 V270 Q438 245 446 270 V435"/>
                    <rect x="0" y="435" width="540" height="24"/>
                </svg>

                <svg class="ba-contour" viewBox="0 0 700 480" xmlns="http://www.w3.org/2000/svg"
                     fill="none" stroke="#47708F" stroke-width="1">
                    <path d="M0 430 C100 350 170 460 290 390 S500 320 700 370"/>
                    <path d="M0 400 C100 320 170 430 290 360 S500 290 700 340"/>
                    <path d="M0 370 C100 290 170 400 290 330 S500 260 700 310"/>
                    <path d="M0 340 C100 260 170 370 290 300 S500 230 700 280"/>
                    <path d="M0 310 C100 230 170 340 290 270 S500 200 700 250"/>
                </svg>

                <div class="ba-hero-content">
                    <div class="ba-eyebrow"></div>
                    <h1 class="ba-hero-title">
                        <span>Tableau de bord</span>
                        <span>économique</span>
                    </h1>
                    <div class="ba-hero-subtitle">
                        Données, indicateurs et analyses économiques de la {INSTITUTION}
                    </div>
                    <div class="ba-hero-features">
                        <div class="ba-feature">
                            <div class="ba-feature-icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
                                    <line x1="5" y1="20" x2="5" y2="11"/>
                                    <line x1="11" y1="20" x2="11" y2="6"/>
                                    <line x1="17" y1="20" x2="17" y2="14"/>
                                    <line x1="3" y1="20" x2="20" y2="20"/>
                                </svg>
                            </div>
                            <div class="ba-feature-label">Indicateurs<br/>économiques</div>
                        </div>
                        <div class="ba-feature">
                            <div class="ba-feature-icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M12 3v9l7.5 4.3A9 9 0 1 0 12 3z"/>
                                    <path d="M12 12L4.5 16.3"/>
                                </svg>
                            </div>
                            <div class="ba-feature-label">Analyses &amp;<br/>statistiques</div>
                        </div>
                        <div class="ba-feature">
                            <div class="ba-feature-icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="4,17 9,10 13,14 20,5"/>
                                    <polyline points="15,5 20,5 20,10"/>
                                </svg>
                            </div>
                            <div class="ba-feature-label">Séries<br/>chronologiques</div>
                        </div>
                        <div class="ba-feature">
                            <div class="ba-feature-icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M7 3h7l4 4v14H7z"/>
                                    <path d="M14 3v5h4"/>
                                    <line x1="10" y1="13" x2="15" y2="13"/>
                                    <line x1="10" y1="17" x2="15" y2="17"/>
                                </svg>
                            </div>
                            <div class="ba-feature-label">Publications &amp;<br/>rapports</div>
                        </div>
                    </div>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


# =============================================================================
# PANNEAU DROIT
# =============================================================================

with col_form:

    st.markdown(
        html_block(
            f"""
            <div class="ba-topbar">
                <a class="ba-help" href="{SITE_OFFICIEL}" target="_blank" rel="noopener noreferrer">Site officiel</a>
                <span class="ba-top-divider"></span>
                <div class="ba-language">
                    <span class="active">FR</span>
                    <span>EN</span>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    with st.container(key="ba_login_card"):

        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)

        st.markdown(
            html_block(
                """
                <div class="ba-login-rule"><span></span></div>
                <div class="ba-login-title">Espace institutionnel</div>
                <div class="ba-login-sub">Accédez à votre tableau de bord économique.</div>
                """
            ),
            unsafe_allow_html=True,
        )

        with st.container(key="ba_login_form"):

            identifiant = st.text_input(
                "Nom d'utilisateur",
                placeholder="Votre identifiant",
                key="login_username",
            )

            mot_de_passe = st.text_input(
                "Mot de passe",
                type="password",
                placeholder="Votre mot de passe",
                key="login_password",
            )

            connexion = st.button(
                "Se connecter",
                key="btn_connexion",
                type="secondary",
                use_container_width=True,
            )

            if connexion:
                if not identifiant or not mot_de_passe:
                    st.warning("Veuillez saisir votre nom d'utilisateur et votre mot de passe.")
                elif identifiant in utilisateurs["username"].values:
                    attendu = utilisateurs.loc[
                        utilisateurs["username"] == identifiant, "password"
                    ].values[0]
                    if str(mot_de_passe) == str(attendu):
                        st.session_state.authenticated = True
                        st.session_state.username = identifiant
                        st.rerun()
                    else:
                        st.error("Nom d'utilisateur ou mot de passe invalide.")
                else:
                    st.error("Nom d'utilisateur ou mot de passe invalide.")

            mdp_oublie = st.button("Mot de passe oublié ?", key="mdp_oublie", type="tertiary")

            if mdp_oublie:
                st.info("Veuillez contacter l'administrateur pour réinitialiser votre mot de passe.")

        st.markdown(
            html_block(
                """
                <div class="ba-security">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#D7A943" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z"/>
                        <path d="M9 12l2 2 4-4"/>
                    </svg>
                    <span>Accès sécurisé réservé au personnel autorisé</span>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )


# =============================================================================
# FOOTER
# =============================================================================

st.markdown(
    html_block(
        f"""
        <div class="ba-footer">
            <span>&copy; {datetime.now().year} {INSTITUTION} — Tous droits réservés.</span>
            <span class="ba-footer-right">
                <svg viewBox="0 0 24 24" fill="none" stroke="#91A2B1" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="5" y="11" width="14" height="9" rx="2"/>
                    <path d="M8 11V7a4 4 0 0 1 8 0v4"/>
                </svg>
                Accès réservé au personnel autorisé
            </span>
        </div>
        """
    ),
    unsafe_allow_html=True,
)


# =============================================================================
# REDIRECTION APRÈS AUTHENTIFICATION
# =============================================================================

if st.session_state.get("authenticated", False):
    st.switch_page("Home.py")