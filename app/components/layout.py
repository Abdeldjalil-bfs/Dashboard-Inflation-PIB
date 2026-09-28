"""
Ossature commune des pages internes.

Il n'y a plus de barre latérale Streamlit. L'en-tête porte le logo à gauche et
le compte connecté à droite ; la navigation du module Inflation s'affiche
verticalement à gauche du contenu, et n'apparaît qu'une fois le module ouvert.
"""

import streamlit as st

from config.settings import LOGO_PATH
from config.textes import LIBELLES_PAGES, MODULE_INFLATION, MODULE_PIB
from app.components.theme import GOLD

# Registre unique des pages : clé -> (fichier, icône Material, module).
# Les libellés viennent de config/textes.py. L'ordre des listes MODULES fixe
# l'ordre de la navigation latérale. Tout lien interne (switch_page) passe
# par ce registre : renommer un fichier ne casse aucun lien.
PAGES = {
    "connexion": ("pages/00_Connexion.py", None, None),
    "accueil": ("Home.py", None, None),
    "inflation_vue": ("pages/01_Inflation_Vue_d_ensemble.py", ":material/monitoring:", MODULE_INFLATION),
    "inflation_groupes": ("pages/02_Inflation_Groupes.py", ":material/stacked_bar_chart:", MODULE_INFLATION),
    "inflation_categories": ("pages/03_Inflation_Categories.py", ":material/grid_view:", MODULE_INFLATION),
    "inflation_complementaire": (
        "pages/04_Inflation_Indice_complementaire.py",
        ":material/analytics:",
        MODULE_INFLATION,
    ),
    "inflation_rapport": ("pages/05_Inflation_Rapport.py", ":material/description:", MODULE_INFLATION),
    "inflation_series": ("pages/06_Inflation_Series.py", ":material/show_chart:", MODULE_INFLATION),
    "saisie": ("pages/07_Saisie.py", ":material/edit_note:", None),
    "pib_vue": ("pages/11_PIB_Vue_d_ensemble.py", ":material/monitoring:", MODULE_PIB),
    "pib_offre": ("pages/12_PIB_Offre.py", ":material/factory:", MODULE_PIB),
    "pib_demande": ("pages/13_PIB_Demande.py", ":material/shopping_cart:", MODULE_PIB),
    "pib_rapport": ("pages/14_PIB_Rapport.py", ":material/description:", MODULE_PIB),
    "pib_series": ("pages/15_PIB_Series.py", ":material/show_chart:", MODULE_PIB),
    "pib_ingestion": ("pages/16_PIB_Ingestion.py", ":material/cloud_download:", MODULE_PIB),
}

MODULES = {
    MODULE_INFLATION: [
        "inflation_vue",
        "inflation_groupes",
        "inflation_categories",
        "inflation_complementaire",
        "inflation_rapport",
        "inflation_series",
        "saisie",
    ],
    MODULE_PIB: ["pib_vue", "pib_offre", "pib_demande", "pib_rapport", "pib_series", "pib_ingestion", "saisie"],
}


def libelle_page(cle):
    return LIBELLES_PAGES[cle]


def aller_a(cle):
    """switch_page vers la page `cle` du registre."""
    st.switch_page(PAGES[cle][0])


def icone_utilisateur(taille=18, couleur=GOLD):
    """Silhouette d'utilisateur, dessinée en SVG pour suivre la charte."""
    return (
        "<svg width='" + str(taille) + "' height='" + str(taille) + "' viewBox='0 0 24 24' "
        "fill='none' stroke='" + couleur + "' stroke-width='1.7' "
        "stroke-linecap='round' stroke-linejoin='round'>"
        "<path d='M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2'/>"
        "<circle cx='12' cy='7' r='4'/>"
        "</svg>"
    )


def bandeau():
    """
    Bandeau supérieur : logo en or à gauche, compte connecté à droite.

    Le nom, la pastille et le bouton vivent dans un MÊME conteneur
    horizontal centré verticalement. Les répartir sur des colonnes séparées
    les désalignait dès que la hauteur du bloc de texte changeait.
    """
    col_logo, col_droite = st.columns([3, 5], vertical_alignment="center")

    with col_logo:
        if LOGO_PATH.exists():
            with st.container(key="ba_logo_bandeau"):
                st.image(str(LOGO_PATH), width="stretch")

    with col_droite:
        with st.container(
            key="ba_compte_barre",
            horizontal=True,
            horizontal_alignment="right",
            vertical_alignment="center",
            gap="medium",
        ):
            utilisateur = st.session_state.get("username", "Utilisateur")
            st.markdown(
                "<div class='ba-compte'>"
                "<div class='ba-compte-bloc'>"
                "<div class='ba-compte-role'>Compte connecté</div>"
                "<div class='ba-compte-nom'>" + str(utilisateur).title() + "</div>"
                "</div>"
                "<div class='ba-compte-icone'>" + icone_utilisateur(17) + "</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("Déconnexion", key="btn_deconnexion"):
                st.session_state["authenticated"] = False
                st.session_state.pop("username", None)
                aller_a("connexion")

    st.markdown("<hr class='ba-topbar-rule'/>", unsafe_allow_html=True)


def _navigation(cle_courante, module):
    """
    Navigation verticale, à gauche du contenu, commune aux modules : même
    ossature, seule la liste de pages change (MODULES).

    Renvoie la colonne de contenu : la page fait `with contenu:` pour y écrire.
    Mémorise le module ouvert : la page Saisie, commune aux deux modules,
    affiche ainsi la navigation et les données du module d'où l'on vient.
    """
    st.session_state["module_actif"] = module
    prefixe_cle = "nav_" + module.lower()
    col_nav, col_contenu = st.columns([1, 5.2], gap="medium")

    with col_nav:
        # Un <div> injecté ne peut pas contenir un widget Streamlit : les
        # boutons resteraient à l'extérieur. On passe donc par un conteneur
        # natif à clé, que Streamlit expose au CSS sous .st-key-ba_nav.
        with st.container(key="ba_nav"):
            st.markdown(
                "<div class='ba-nav-titre'>Module<br/>" + module + "</div><div class='ba-nav-filet'></div>",
                unsafe_allow_html=True,
            )

            for cle in MODULES[module]:
                actif = cle == cle_courante
                if (
                    st.button(
                        LIBELLES_PAGES[cle],
                        key=prefixe_cle + "_" + cle,
                        icon=PAGES[cle][1],
                        type="primary" if actif else "tertiary",
                    )
                    and not actif
                ):
                    aller_a(cle)

            st.markdown(
                "<hr style='height:1px;border:0;margin:1rem 0 .7rem 0;"
                "background:linear-gradient(90deg,rgba(188,158,110,0.32),"
                "rgba(188,158,110,0.03));'/>",
                unsafe_allow_html=True,
            )

            if st.button("Modules", key=prefixe_cle + "_retour", type="tertiary", icon=":material/arrow_back:"):
                aller_a("accueil")

    return col_contenu


def demarrer_page(cle, module=None):
    """
    Ossature d'une page interne, dans l'ordre imposé par Streamlit :
    configuration (titre d'onglet = libellé de la page), contrôle
    d'authentification, charte, bandeau, navigation du module. Renvoie la
    colonne de contenu.

    `module` n'est utile que pour la page Saisie, commune aux deux modules.
    """
    from app.components.theme import configurer_page, appliquer_theme
    from app.components.auth import require_auth

    module = module or PAGES[cle][2]
    configurer_page(LIBELLES_PAGES[cle], module)
    require_auth()
    appliquer_theme()
    bandeau()
    return _navigation(cle, module)
