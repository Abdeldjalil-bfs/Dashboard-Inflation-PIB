"""
Textes partagés de l'interface : libellés de modules et de pages, messages
récurrents. Seul endroit où ils sont écrits, pour qu'une page, la
navigation et le titre d'onglet ne divergent jamais.

Aucune date ici : les périodes affichées viennent toujours des données ou de
la date du jour.
"""

INSTITUTION_COMPLEMENT = "de la Banque d'Algérie"

MODULE_INFLATION = "Inflation"
MODULE_PIB = "PIB"

# Clé de page -> libellé (identique dans la navigation, le titre de page et
# le titre d'onglet).
LIBELLES_PAGES = {
    "inflation_vue": "Vue d'ensemble",
    "inflation_groupes": "Groupes",
    "inflation_categories": "Catégories",
    "inflation_complementaire": "Indice complémentaire",
    "inflation_rapport": "Rapport",
    "inflation_series": "Séries",
    "saisie": "Saisie",
    "pib_vue": "Vue d'ensemble",
    "pib_offre": "Offre",
    "pib_demande": "Demande",
    "pib_rapport": "Rapport",
    "pib_series": "Séries",
    "pib_ingestion": "Ingestion de données",
}

ACCUEIL = {
    "titre": "Tableau de bord économique",
    "sous_titre": "Indicateurs macroéconomiques de référence de la Banque d'Algérie, mis à jour à chaque publication officielle.",
    "eyebrow": "Module",
    "bouton": "Ouvrir le module",
    "inflation_titre": "Inflation",
    "inflation_phrase": (
        "Suivi des prix à la consommation à l'échelle nationale et pour le Grand Alger : indices, "
        "glissements mensuels et annuels, contributions par groupe de produits. Historique complet, "
        "comparaisons sur mesure et rapport prêt à diffuser."
    ),
    "inflation_points": ("National & Grand Alger", "Contributions par groupe", "Rapport PDF"),
    "inflation_indicateur": "inflation annuelle, national",
    "pib_titre": "Produit intérieur brut",
    "pib_phrase": (
        "Comptes nationaux trimestriels : croissance réelle du PIB, contributions de l'offre (secteurs "
        "d'activité) et de la demande (consommation, investissement, échanges extérieurs). Lecture "
        "hydrocarbures / hors hydrocarbures et rapport prêt à diffuser."
    ),
    "pib_points": ("Offre & demande", "Hydrocarbures / hors hydrocarbures", "Rapport PDF"),
    "pib_indicateur": "croissance réelle sur un an",
    "vide_inflation": "Aucune donnée d'inflation calculée pour le moment.",
    "vide_pib": "Aucune donnée PIB en base pour le moment.",
}

MESSAGES = {
    "donnees_indisponibles": "Les données de cette page sont momentanément indisponibles.",
    "graphique_indisponible": "Ce graphique ne peut pas être affiché avec les données actuelles.",
    "fichier_absent": "Le fichier de données attendu est introuvable : {fichier}.",
    "base_vide": "La base ne contient encore aucune donnée pour ce module.",
    "acces_reserve": "Cette action est réservée aux profils administrateurs.",
    "connexion_requise": "Veuillez vous connecter pour accéder au tableau de bord.",
}
