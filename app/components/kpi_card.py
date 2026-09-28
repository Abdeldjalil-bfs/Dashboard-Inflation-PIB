"""Carte d'indicateur clé, conforme à la charte (app/components/theme.py)."""

from app.components.theme import POSITIF, NEGATIF, TEXTE_ATTENUE

# Fonds des pastilles de variation : la teinte sémantique, très diluée.
_FOND_POSITIF = "rgba(63, 191, 127, 0.13)"
_FOND_NEGATIF = "rgba(226, 99, 91, 0.13)"
_FOND_NEUTRE = "rgba(159, 179, 194, 0.12)"


def _nombre(valeur, decimales):
    """Séparateur de milliers fin et virgule décimale, à la française."""
    texte = ("{:,.%df}" % decimales).format(valeur)
    return texte.replace(",", " ").replace(".", ",")


def carte_kpi(
    libelle,
    valeur,
    delta,
    unite="%",
    note="vs période précédente",
    unite_delta="pp",
    favorable_si_hausse=None,
    decimales=2,
):
    """
    Libellé en micro-capitales atténuées, valeur en grand caractère doré,
    variation dans une pastille colorée.

    `favorable_si_hausse` règle la lecture économique de la couleur :
      None  -> la couleur suit le sens (vert en hausse, rouge en baisse),
               comportement historique du module Inflation ;
      True  -> hausse favorable (croissance) : vert en hausse ;
      False -> hausse défavorable (prix, déflateur) : rouge en hausse.
    Une valeur ou une variation absente (None) s'affiche « — ».

    Retourne du HTML à passer à st.markdown(..., unsafe_allow_html=True).
    """
    # NaN (trimestre non publié) se lit comme une absence de valeur.
    valeur = None if valeur is None or valeur != valeur else valeur
    delta = None if delta is None or delta != delta else delta
    if delta is None:
        fleche, couleur, fond, texte_delta = "", TEXTE_ATTENUE, _FOND_NEUTRE, "—"
    else:
        hausse = delta >= 0
        favorable = hausse if favorable_si_hausse in (None, True) else not hausse
        fleche = "▲ " if hausse else "▼ "
        couleur = POSITIF if favorable else NEGATIF
        fond = _FOND_POSITIF if favorable else _FOND_NEGATIF
        texte_delta = _nombre(abs(delta), 2) + " " + unite_delta

    texte_valeur = "—" if valeur is None else _nombre(valeur, decimales)

    return (
        "<div class='ba-kpi'>"
        "<div class='ba-kpi-label'>" + str(libelle) + "</div>"
        "<div class='ba-kpi-value'>" + texte_valeur + "<span class='ba-kpi-unit'>" + unite + "</span></div>"
        "<div class='ba-kpi-delta' style='color:"
        + couleur
        + ";background:"
        + fond
        + ";'>"
        + fleche
        + texte_delta
        + "</div>"
        "<div class='ba-kpi-delta-note'>" + note + "</div>"
        "</div>"
    )


# Ancien nom conservé pour ne rien casser dans les pages existantes.
kpi_card = carte_kpi
