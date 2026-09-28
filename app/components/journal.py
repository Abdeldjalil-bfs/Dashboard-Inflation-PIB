"""Raccourcis de journalisation côté pages (utilisateur connecté ajouté)."""

import streamlit as st

from backend.common import journal as _j


def journaliser(categorie, message):
    _j.evenement(categorie, message, st.session_state.get("username", ""))


def journaliser_erreur(categorie, exc):
    _j.erreur(categorie, exc, st.session_state.get("username", ""))


def signaler(categorie, exc, message, niveau="error"):
    """
    Message humain à l'écran, détail technique dans le journal. Les erreurs
    de validation (ValueError) levées par le projet portent déjà un texte
    lisible en français : il est ajouté au message. Toute autre erreur reste
    dans le journal, jamais à l'écran.
    """
    journaliser_erreur(categorie, exc)
    texte = message
    if isinstance(exc, ValueError) and str(exc):
        texte += " " + str(exc)
    getattr(st, niveau)(texte)
