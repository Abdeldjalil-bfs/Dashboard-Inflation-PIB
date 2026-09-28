"""
Journal de l'application (module logging standard).

Événements tracés : connexion, ingestion, saisie, génération de rapport,
erreurs. Les pages n'affichent jamais de trace technique : elles montrent un
message humain et consignent le détail ici (logs/dashboard.log, chemin dans
config/settings.py).
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_NOM = "dashboard"


def journal() -> logging.Logger:
    """Logger unique du projet, configuré une seule fois par processus."""
    logger = logging.getLogger(_NOM)
    if not logger.handlers:
        from config.settings import FICHIER_JOURNAL

        logger.setLevel(logging.INFO)
        try:
            os.makedirs(os.path.dirname(str(FICHIER_JOURNAL)), exist_ok=True)
            gestionnaire = RotatingFileHandler(
                str(FICHIER_JOURNAL), maxBytes=2_000_000, backupCount=5, encoding="utf-8"
            )
        except OSError:
            gestionnaire = logging.StreamHandler()
        gestionnaire.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(gestionnaire)
        logger.propagate = False
    return logger


def evenement(categorie: str, message: str, utilisateur: str = "") -> None:
    """Événement métier : connexion, ingestion, saisie, rapport."""
    journal().info("[%s] %s%s", categorie, message, (" (utilisateur : %s)" % utilisateur) if utilisateur else "")


def erreur(categorie: str, exc: BaseException, utilisateur: str = "") -> None:
    """Erreur avec sa trace complète, pour le diagnostic (jamais affichée à l'écran)."""
    journal().error(
        "[%s] %s%s", categorie, exc, (" (utilisateur : %s)" % utilisateur) if utilisateur else "", exc_info=exc
    )
