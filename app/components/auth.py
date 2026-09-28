"""Contrôle d'accès des pages : authentification et profil administrateur."""

import streamlit as st

from config.textes import MESSAGES


def require_auth():
    """Redirige vers la page de connexion si l'utilisateur n'est pas authentifié."""
    if not st.session_state.get("authenticated", False):
        from app.components.layout import aller_a

        aller_a("connexion")
        st.stop()


def est_admin() -> bool:
    """
    Retourne toujours True : pas de distinction de profil, authentification
    simple par fichier Excel (username/password en clair) comme avant le
    passage bcrypt/rôles. Fonction conservée pour ne pas casser les pages
    qui l'appellent (07_Saisie.py, 16_PIB_Ingestion.py) ; tout compte
    authentifié a un accès complet.
    """
    return True


def exiger_admin() -> bool:
    """Affiche un message et renvoie False si l'utilisateur n'est pas admin."""
    if est_admin():
        return True
    st.info(MESSAGES["acces_reserve"])
    return False
