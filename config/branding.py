"""
Constantes de charte partagées.

Seul endroit où la palette et les polices de la Banque d'Algérie sont
définies. Importé des deux côtés de l'architecture :
  - app/components/theme.py      -> CSS du tableau de bord Streamlit
  - backend/inflation/reporting.py -> CSS du rapport PDF

Ce fichier ne contient que des données : aucune dépendance à Streamlit ni à
un moteur de rendu.
"""

# --- Fond : dégradé vertical navy -------------------------------------------
COLOR_NAVY_DARKEST = "#081F33"
COLOR_NAVY_DEEP = "#08283D"
COLOR_NAVY_LIGHT = "#083D54"

# --- Or institutionnel : seule couleur d'accent forte ------------------------
COLOR_GOLD = "#BC9E6E"
COLOR_GOLD_LIGHT = "#C6A873"
COLOR_GOLD_DARK = "#9E8357"

# --- Cyan technique, employé avec parcimonie dans les visualisations ---------
COLOR_CYAN = "#087A9C"
COLOR_CYAN_MID = "#0A8FB5"
COLOR_CYAN_LIGHT = "#1AA6D1"

# --- Couleurs sémantiques des variations (réservées) -------------------------
COLOR_POSITIF = "#3FBF7F"
COLOR_NEGATIF = "#E2635B"

# --- Encres ------------------------------------------------------------------
COLOR_TEXTE = "#F4F6F8"
COLOR_TEXTE_ATTENUE = "#9FB3C2"

# Le PDF s'imprime sur papier : l'encre s'inverse, la charte non.
COLOR_PAPIER = "#FFFFFF"
COLOR_PAPIER_ALT = "#F6F7F9"
COLOR_ENCRE = "#10202F"
COLOR_ENCRE_ATTENUEE = "#5A6C7C"

# --- Polices -----------------------------------------------------------------
FONT_FAMILY_TITRE = "Montserrat, 'Segoe UI', sans-serif"
FONT_FAMILY_TEXTE = "Inter, 'Segoe UI', sans-serif"
FONT_GOOGLE_IMPORT = (
    "https://fonts.googleapis.com/css2"
    "?family=Montserrat:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap"
)

# --- Palette catégorielle des séries ----------------------------------------
# 8 emplacements dérivés des teintes de la charte (cyan 226°, or 79°), répartis
# tous les 45°. Validée sur fond sombre #08283D : bande de clarté OKLCH,
# plancher de chroma, séparation daltonisme (ΔE ≥ 9,5) et contraste ≥ 3:1.
# L'ordre est FIXE : une catégorie garde sa couleur quel que soit le filtre.
PALETTE_SERIES = [
    "#0094BD",  # cyan
    "#C3608A",  # rose
    "#6B9635",  # vert olive
    "#5E82D7",  # bleu
    "#C96643",  # orange
    "#0C9C82",  # teal
    "#9F6DC2",  # violet
    "#AF7B08",  # ambre
]

# --- Identité ----------------------------------------------------------------
INSTITUTION = "Banque d'Algérie"
SITE_OFFICIEL = "https://www.bank-of-algeria.dz"
