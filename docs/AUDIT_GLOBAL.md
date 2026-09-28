# Audit global du projet (septembre 2026)

État des lieux dressé avant la refonte : ce qui existe, ce qui est mort, en
double ou mal placé. Les décisions prises figurent en fin de document.

## 1. Constats bloquants

1. **[Certain] Un clone neuf ne pouvait pas calculer l'inflation.**
   `pipeline_global()` lisait la feuille `core`, qui n'existe ni dans le
   fichier brut ni dans le dépôt : elle ne vivait que dans le fichier de
   travail local d'un poste. Corrigé : `creer_feuille_core_si_absente()` la
   reconstruit depuis l'onglet `IPC_Catégories` de `Data_inflation.xlsx`.
2. **[Certain] Le « bug » de portée est une limite des données.** Les
   feuilles `categories`, `core` et `Produits_agricoles_frais` décrivent le
   panier **Grand Alger** : l'IPC de `categories` vaut celui de Grand Alger
   (211,97 en juin 2020, contre 225,36 pour le national), et le détail
   national des agricoles frais est à zéro dans la source. Il n'existe donc
   aucune décomposition core / non-core nationale. De plus, le graphique de
   contributions de la vue d'ensemble lisait `categories` quelle que soit la
   portée. Décision validée : en National, il affiche les contributions des
   huit groupes nationaux, avec une note.
3. **[Certain] Mots de passe en clair et versionnés** (`data/users.xlsx`),
   alors que `backend/auth/users.py` (prévu pour bcrypt) est vide.
4. **[Certain] Rapport PDF inutilisable sous Windows standard** : WeasyPrint
   exige GTK/Pango ; le repli par navigateur dépend d'Edge ou de Chrome.
5. **[Certain] Pages PIB et base CNT déconnectées** : les pages lisent les
   classeurs, la base `cnt_pib` est vide (voir `AUDIT_INGESTION_CNT.md`).

## 2. Code mort ou superflu

| Élément | Constat | Traitement |
|---|---|---|
| `app/pages/8_PIB_Previsions.py` | Page « en préparation », hors navigation | Supprimée |
| `backend/pib/forecasting/*` | Quatre fichiers vides | Supprimés |
| `backend/auth/users.py` | Vide | Implémenté (bcrypt, rôles) |
| `tests/test_inflation_calculator.py`, `tests/test_pib_forecasting.py` | Vides | Premier écrit, second supprimé |
| `tracer_repartition_panier`, `tracer_poids_et_contribution`, `repartition_ponderations`, `repartition_core_noncore`, `contributions_core_noncore` | Graphiques de poids du panier | Supprimés (§ 5) |
| `backend/inflation/visualizer.py` `__main__` | Démo avec dates et fichier en dur | Supprimé |
| `app/components/actions.py` | `bouton_rapport_pdf` et `bouton_import_donnees` inutilisés | Supprimé |
| `app/assets/icone-connexion-…avif` | Non référencé | Supprimé |
| `dashboard_inflation_pib.egg-info/` | Artefact d'installation versionné | Retiré du suivi |
| `.vscode/` | Réglage d'éditeur personnel | Retiré du suivi |

## 3. Mal placé ou fragile

- Sauvegarde `Fichier_de_donnes_secours.xlsx` mêlée aux sources, déplacée
  dans `data/sauvegardes/`.
- Logos dans `app/assets/`, fonds de carte à créer : tout est regroupé dans
  `assets/` (racine), avec un sous-dossier `assets/geo/`.
- Gabarits du rapport dans `backend/inflation/templates/` alors qu'ils
  servent aussi au PIB : déplacés dans `templates/`.
- Sorties générées (`outputs/`) : conservées, ignorées par Git.
- Aucun `os.chdir` ; tous les chemins passent déjà par `config/settings.py`,
  à l'exception de liens `switch_page` écrits en dur dans plusieurs pages.
  Ils sont remplacés par un registre de pages unique.
- Dates en dur dans les textes : annexe du rapport (« août 2025 »), valeur
  par défaut `date_fin="2026-07"` de deux fonctions de calcul, démo du
  visualizer.

## 4. Décisions validées

| Sujet | Décision |
|---|---|
| Moteur PDF | ReportLab (100 % Python), derrière une interface unique dans `reporting.py` |
| Mots de passe | Hachage bcrypt ; fichier réel hors du dépôt, exemple sans vrai compte |
| Profil admin | Colonne `role` (admin / lecteur) ; sans colonne, tout le monde est admin |
| Source PIB | Classeurs ONS chargés comme « millésime 0 » ; les pages lisent `cnt_pib_derniere` |
| Portée National | Contributions des huit groupes nationaux, avec une note |

## 5. Points laissés ouverts (hypothèses retenues)

- « Graphiques du poids du panier » : interprété comme
  `tracer_repartition_panier` (Groupes, Catégories) et
  `tracer_poids_et_contribution` (Vue d'ensemble, qui répète aussi une
  contribution). Les graphiques d'évolution et de contribution d'origine
  sont conservés.
- Fonds de carte : geoBoundaries. Pays et wilayas sous licence ODbL ;
  communes sous CC BY-SA 2.0, dérivées d'OpenStreetMap. Attribution dans le
  README ; à valider si l'institution a une politique de licences.
- Ordre des pages PIB : la liste du cahier des charges est tronquée.
  Retenu, en miroir de l'Inflation : Vue d'ensemble, Offre, Demande,
  Rapport, Séries, Ingestion de données, Saisie.

## Lacune de données constatée (septembre 2026)

Dans `Fichier_de_donnes.xlsx`, feuille `Produits_agricoles_frais`, quatre composantes
(Viandes_de_poulet, Œufs, Légumes_frais, Fruits_frais) ne sont plus renseignées après
juillet 2025. L'indice non-core Grand Alger et ses glissements ne sont donc pas calculables
depuis août 2025 : la carte KPI « Non-core » affiche « données indisponibles » et les
contributions core / non-core s'arrêtent à cette date. Correction attendue côté données
(saisie des quatre séries), pas côté code.
