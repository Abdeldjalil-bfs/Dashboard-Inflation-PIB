# Tableau de bord Inflation et PIB — Banque d'Algérie

Application Streamlit de suivi de deux indicateurs macroéconomiques :

- **Inflation** : indice des prix à la consommation (IPC), mensuel, pour le
  Grand Alger et l'ensemble du territoire national.
- **PIB** : comptes nationaux trimestriels de l'ONS (croissance, déflateur,
  contributions de l'offre et de la demande), avec ingestion des rapports
  CNT publiés sur ons.dz.

Chaque module produit un rapport PDF éditorial, rédigé par un moteur de
règles déterministe (aucun modèle de langage).

| Accueil | Inflation — vue d'ensemble |
|---|---|
| ![Accueil](docs/captures/accueil.png) | ![Inflation](docs/captures/inflation_vue_densemble.png) |
| **PIB — offre** | **PIB — ingestion de données** |
| ![Offre](docs/captures/pib_offre.png) | ![Ingestion](docs/captures/pib_ingestion_de_donnees.png) |

---

## 1. Démarrage rapide

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux / macOS : source .venv/bin/activate)
pip install -r requirements.txt   # installe aussi le projet lui-même
python scripts/creer_utilisateur.py mon.identifiant admin
streamlit run app/Home.py
```

L'application s'ouvre sur http://localhost:8501. Aucune bibliothèque système
n'est nécessaire (pas de GTK, pas de navigateur pour le PDF) : Python 3.11 ou
plus récent suffit, sous Windows comme sous Linux ou macOS.

Au premier lancement :

- le fichier de calculs de l'inflation se crée avec
  `python -c "from backend.inflation.calculator import pipeline_global; from config.settings import FICHIER_DONNEES; pipeline_global(str(FICHIER_DONNEES))"`,
  ou depuis la page **Saisie** (bouton « Recalculer les indicateurs ») ;
- la base PIB (`data/dashboard.db`) se crée seule, à la première ouverture
  d'une page PIB, à partir des classeurs ONS.

---

## 2. Architecture

```
app/                      Interface Streamlit (mise en page et filtres uniquement)
  Home.py                 Accueil : choix du module
  pages/                  Une page par fichier ; préfixe = ordre (00 connexion, 0x Inflation, 1x PIB)
  components/             Briques partagées : thème, en-tête et navigation (registre des
                          pages), cartes KPI, graphique + tableau, explorateur de séries,
                          stepper, journal, contrôle d'accès
backend/                  Toute la logique, sans dépendance à Streamlit
  inflation/              calculator (IPC, glissements, contributions), visualizer (Plotly),
                          portee (choix des séries par portée), reporting (rapports PDF,
                          interface unique de rendu), data_entry, anomaly_detection, series
  pib/                    lecture_ons (classeurs ONS), calculator (croissance, déflateur,
                          contributions, ratios), visualizer, ons_cnt (extraction des PDF CNT),
                          base_cnt (base SQLite, millésime 0), series, data_entry
  common/                 moteur_pdf (ReportLab), statistiques, journal, excel_io
  auth/users.py           Comptes : bcrypt et profils
config/                   settings.py (tous les chemins), textes.py (libellés partagés),
                          branding.py (charte), *.json (pondérations, règles narratives,
                          schéma PIB, anomalies)
data/
  raw/inflation/          Sources IPC (Fichier_de_donnes.xlsx, Data_inflation.xlsx)
  raw/pib/                Classeurs ONS PIB_TR_S.xlsx (offre), PIB_TR_D.xlsx (demande)
  processed/              Fichiers de calculs générés (hors dépôt)
  sauvegardes/            Copies de secours des sources
  dashboard.db            Base CNT (générée, hors dépôt)
  users.xlsx              Comptes (hors dépôt) ; modèle : users.example.xlsx
assets/                   Logos, polices (Montserrat, Inter), fonds de carte GeoJSON
scripts/                  Création de comptes, migration bcrypt, préparation des fonds de carte
tests/                    Suite pytest (données factices dédiées)
docs/                     Audits et décisions de conception, captures d'écran
outputs/                  Graphiques PNG et rapports PDF générés (hors dépôt)
logs/                     Journal de l'application (hors dépôt)
```

Principes : les pages n'effectuent aucun calcul ; tous les chemins passent
par `config/settings.py` (aucun chemin relatif fragile, aucun `os.chdir`) ;
tout lien interne passe par le registre de pages de
`app/components/layout.py` ; les libellés partagés vivent dans
`config/textes.py`.

---

## 3. Installation détaillée

### Windows

1. Installer Python 3.11+ depuis python.org (cocher « Add python.exe to PATH »).
2. Dans un terminal PowerShell, à la racine du projet :
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Créer un compte, puis lancer l'application (voir § 1).

### Linux / macOS

Identique, avec `source .venv/bin/activate`.

### Développement

```bash
pip install -r requirements-dev.txt   # pytest, ruff, pymupdf (lecture des PDF dans les tests)
```

### Docker

```bash
docker build -t dashboard-bda .
docker run -p 8501:8501 -v "$PWD/data:/app/data" dashboard-bda
```

### Déploiement (Streamlit Community Cloud, Docker en production)

Voir [`docs/DEPLOIEMENT.md`](docs/DEPLOIEMENT.md) : dépendances par hôte,
persistance des données (base PIB, comptes, saisies), provisionnement de
`data/users.xlsx`, et procédure pas à pas pour les deux options.

---

## 4. Configuration

| Fichier | Rôle |
|---|---|
| `config/settings.py` | Tous les chemins (données, base SQLite, sorties, journal) ; URL, délai et vérification SSL d'ons.dz |
| `config/textes.py` | Libellés des modules et des pages (navigation = titre de page = titre d'onglet), messages récurrents |
| `config/branding.py` | Palette navy / or, polices, palette des séries |
| `config/weights.json` | Pondérations des paniers IPC |
| `config/narrative_rules.json` | Seuils, gabarits et structure éditoriale des rapports |
| `config/pib_config.json` | Schéma PIB : correspondance des colonnes ONS, secteurs, postes, correspondance des postes CNT, tolérance |
| `config/anomaly_rules.json` | Seuils de détection d'anomalies à la saisie |
| `.streamlit/config.toml` | Thème sombre forcé, options serveur, navigation Streamlit masquée |
| `.env.example` | Variables facultatives (test réseau réel) |

### Utilisateurs et mots de passe

- Fichier `data/users.xlsx`, **hors dépôt Git** ; colonnes `username`,
  `password` (en clair). Modèle à jour : `data/users.example.xlsx`.
- Pas de distinction de profil : tout compte authentifié a accès à
  l'ensemble de l'application (`app/components/auth.py::est_admin()`).
- Créer ou ajouter un compte (aucun script dédié aujourd'hui — voir
  `docs/DEPLOIEMENT.md` §5 pour l'exemple complet) :
  ```python
  import pandas as pd
  pd.DataFrame({"username": ["mon.identifiant"], "password": ["..."]}).to_excel(
      "data/users.xlsx", index=False
  )
  ```
  `scripts/creer_utilisateur.py` et `scripts/migrer_mots_de_passe.py` datent
  de l'ancien système à bcrypt/rôles et ne sont plus compatibles avec ce
  format : ne pas les utiliser.
- Toutes les pages internes exigent une connexion.
- Journal : `logs/dashboard.log` (connexions, ingestions, saisies, rapports, erreurs).

---

## 5. Données

### Inflation (mensuelle)

- `data/raw/inflation/Fichier_de_donnes.xlsx` : une feuille par panier
  (`Grand_Alger`, `national`, `categories`, `Produits_agricoles_frais`,
  `Alimentations_Boissons_non_alco`), colonne `date` puis une colonne
  d'indice par poste.
- `data/raw/inflation/Data_inflation.xlsx` : onglets ONS larges
  (`Alger 2001`, `National_2001`, `IPC_Catégories`, `FCI_REG`), qui
  prolongent l'historique, reconstruisent la feuille `core` et fournissent les
  indices nationaux complémentaires (réglementés, fort contenu d'import,
  sous-jacente 2).
- `pipeline_global()` produit `data/processed/Fichier_de_donnes_et_calculs.xlsx`.
  Les pages ne lisent que ce fichier.
- **Portées** : `categories`, `core` et `Produits_agricoles_frais` décrivent le
  panier **Grand Alger** (l'IPC de `categories` égale celui de Grand Alger).
  La décomposition core / non-core n'existe donc pas au niveau national : en
  portée National, la vue d'ensemble affiche les séries nationales
  (indice global, sous-jacente 2, réglementés, fort contenu d'import) et les
  contributions des huit groupes. `backend/inflation/portee.py` est le seul
  endroit qui choisit les séries selon la portée.

### PIB (trimestriel)

- Classeurs ONS `PIB_TR_S.xlsx` (offre) et `PIB_TR_D.xlsx` (demande) :
  onglets `PIB_N` (prix courants, millions DA) et `PIB_R` (volumes aux prix de
  l'année précédente chaînés), en-tête en ligne 4. Ils sont pilotés par
  formules : l'application ne les réécrit jamais.
- **Base SQLite** `data/dashboard.db` :
  - `cnt_pib` : toutes les versions de chaque observation, clé
    `(rapport, bloc, poste, annee, trimestre)` ;
  - `cnt_imports` : rapports importés (date, nombre de lignes) ;
  - vue `cnt_pib_derniere` : dernière version de chaque observation. **C'est
    elle que lisent toutes les pages PIB.**
- **Millésime 0** : les classeurs ONS sont chargés en base comme le rapport
  `0000T0` (« Socle ONS »). Un rapport CNT ingéré (`AAAATn`) prend donc
  toujours la main sur les trimestres qu'il couvre, et l'historique depuis
  2001 reste disponible. Les volumes sont reconstruits par chaînage des taux
  t/t−4, exactement comme l'ONS construit `PIB_R` (reproduction vérifiée à
  1e-15 près par les tests).
- Les saisies PIB sont consignées dans `data/raw/pib/PIB_saisies.xlsx`, puis
  le socle est reconstruit en une transaction.

---

## 6. Méthodologie et formules

### Inflation

- **IPC pondéré** : `IPC_t = Σ w_i · I_i,t / Σ w_i` (poids de `weights.json`).
- **Glissement mensuel** : `(IPC_t / IPC_t−1 − 1) × 100` ; **annuel** : `(IPC_t / IPC_t−12 − 1) × 100`.
- **Contribution** d'un poste, en points de pourcentage :
  `C_i,t = w_i · (I_i,t − I_i,t−k) / (Σ w · IPC_t−k) × 100` ; la somme des
  contributions reconstitue l'inflation du panier (tolérance 0,1 pt,
  `narrative_rules.json`).
- **Core / non-core** : core = produits alimentaires industriels, biens
  manufacturés, services ; non-core = produits agricoles frais (panier
  Grand Alger).

### PIB

Les données ONS contiennent des valeurs nominales et des taux de croissance
en volumes chaînés (t/t−4), pas de volumes additifs en niveau. D'où :

- **Croissance** : glissement annuel `g = (Y_t / Y_t−4 − 1) × 100`, trimestriel `(Y_t / Y_t−1 − 1) × 100`.
- **Déflateur** : `PIB nominal / PIB réel × 100` ; inflation implicite = son glissement.
- **Contributions (méthode SCN 2008, structure nominale)** :
  `C_i = (VA_nominale_i,t−4 / PIB_nominal_t−4) × g_réel_i`. La méthode est
  détectée à partir des données (titre de l'onglet réel et test
  d'additivité), non supposée.
- **Contrôle de cohérence** : somme des contributions face à la croissance
  publiée, avec une tolérance de 0,1 pt (`pib_config.json`). En volumes
  chaînés, un écart structurel subsiste (non-additivité, taux ONS arrondis à
  0,1 pt) : il est affiché comme « écart de chaînage ».
- **Optique demande** : contributions de la consommation des ménages, de la
  consommation publique, de la FBCF et des exportations nettes (X − M, les
  importations avec un signe négatif). La ligne « variations de stocks et
  écart statistique » est calculée en résiduel : la variation de stocks en
  volume publiée par l'ONS est inexploitable.
- **Ratios** (en nominal) : taux d'investissement `FBCF / PIB`, taux
  d'ouverture `(X + M) / PIB`.
- **Hors hydrocarbures** : moyenne des croissances des autres secteurs,
  pondérée par leur VA nominale en t−4 (la soustraction n'a pas de sens en
  volumes chaînés).

Voir aussi `docs/AUDIT_PIB.md`, `docs/AUDIT_INGESTION_CNT.md` et `docs/AUDIT_GLOBAL.md`.

---

## 7. Les pages

Chaque page suit la même ossature : en-tête (logo doré, compte connecté),
navigation latérale du module, une ligne de filtres, puis les graphiques,
chacun suivi de son tableau de valeurs exportable en CSV.

### Module Inflation

| Page | Contenu |
|---|---|
| Vue d'ensemble | Filtres portée, glissement et période ; carte de la portée (hors ligne, contour de l'Algérie en or, communes d'Alger en mode Grand Alger) ; trois KPI ; évolution ; contributions. La portée met tout à jour en même temps. |
| Groupes | Évolution et contributions des huit groupes, Grand Alger ou national. |
| Catégories | Biens alimentaires, manufacturés et services (panier Grand Alger). |
| Indice complémentaire | Réglementés, fort contenu d'import, sous-jacente 2 (national). |
| Rapport | Génération et téléchargement du rapport mensuel PDF. |
| Séries | Explorateur : périmètre, mesure, séries, représentation (lignes, barres, base 100, empilements), synthèse et export. |
| Saisie | Insertion, modification et recalcul, avec détection d'anomalies (admin). |

### Module PIB

| Page | Contenu |
|---|---|
| Vue d'ensemble | Quatre KPI (PIB nominal, croissance réelle, croissance hors hydrocarbures, déflateur), croissance hydrocarbures / hors hydrocarbures / PIB total, croissance nominale face à la croissance réelle. |
| Offre | Waterfall des contributions sectorielles, structure du PIB à 100 %, croissance QoQ et YoY par branche. |
| Demande | Contributions des emplois finals (avec le résiduel), taux d'investissement et d'ouverture. |
| Rapport | Rapport trimestriel PDF. |
| Séries | Même explorateur que l'Inflation, sur les blocs de la base CNT. |
| Ingestion de données | Import d'un rapport CNT d'ons.dz en cinq étapes (voir § 8). |
| Saisie | Insertion, modification et suppression d'une valeur trimestrielle (admin). |

---

## 8. Saisie et ingestion

**Saisie (Inflation)** : un mois, panier par panier (tout ou rien) ; chaque
valeur est comparée à l'historique par un z-score robuste (niveau et
variation, même mois des années précédentes). Un écart important exige une
confirmation explicite.

**Saisie (PIB)** : journal des saisies, même détection d'anomalies adaptée au
trimestre, reconstruction du socle en base.

**Ingestion CNT** (page « Ingestion de données ») :

1. **Sélection** de l'année et du trimestre ; bouton « Rechercher un nouveau
   rapport » (test léger sur ons.dz) ; dépôt manuel d'un PDF si le site est
   injoignable.
2. **Extraction** des quatre tableaux du PDF (`backend/pib/ons_cnt.py`) ;
   l'Excel est téléchargeable dès cette étape.
3. **Contrôles qualité** : une *erreur* bloque l'injection, un
   *avertissement* informe (dont les postes non reconnus par la table de
   correspondance).
4. **Comparaison** avec la base : observations nouvelles et révisées.
5. **Validation** explicite, puis injection atomique (tout ou rien) et
   rejouable (réinjecter un rapport ne remplace que ce rapport).

---

## 9. Rapports PDF

- Moteur **ReportLab** (100 % Python), derrière l'interface unique
  `rendre_document()` de `backend/inflation/reporting.py`. Aucune autre partie
  du code ne dépend du moteur.
- Contenu : couverture avec logo doré, synthèse, sections, annexe
  méthodologique, traçabilité et pagination « page x / N ». Les KPI suivent la
  lecture économique : hausse de l'inflation en rouge, hausse de la croissance
  en vert.
- Tous les textes (gabarits, seuils, titres, légendes, annexe) viennent de
  `config/narrative_rules.json` : modifier ce fichier suffit pour adapter la
  rédaction. Un test vérifie qu'aucune phrase n'est codée en dur dans
  `reporting.py`.
- Graphiques : exportés en PNG par kaleido. Si l'export échoue, le rapport se
  génère quand même, avec un message à la place du graphique.

---

## 10. Tests

```bash
pip install -r requirements-dev.txt
pytest                   # toute la suite
ruff check . && ruff format --check .
```

La suite couvre :

- les calculs (IPC pondéré, MoM et YoY, somme des contributions, core et
  non-core, croissance PIB, déflateur, contributions PIB) ;
- la non-régression de la portée ;
- l'ingestion ONS sur un PDF factice local (extraction, contrôles, révisions
  entre millésimes, idempotence, atomicité, réseau coupé, rapport
  introuvable) ;
- la base (millésime 0 identique aux classeurs) ;
- la génération des PDF ;
- le moteur narratif ;
- les pages (`AppTest` : chargement, authentification requise, titres de
  graphiques renseignés) ;
- l'authentification (fichier Excel en clair, accès requis sur toutes les pages internes) ;
- la qualité des textes (aucune date en dur, aucun texte provisoire).

Test réseau réel sur ons.dz, facultatif : `ONS_CNT_TEST_RESEAU=1 pytest -k reel`.

---

## 11. Dépannage

| Symptôme | Cause et solution |
|---|---|
| Erreur GTK / Pango au rapport | Ancienne version : WeasyPrint exigeait des bibliothèques système absentes de Windows. Il a été remplacé par ReportLab ; mettez le projet à jour. |
| Graphiques absents du PDF | Export PNG kaleido indisponible. Versions épinglées : 0.2.1, ou 0.1.0.post1 sous Windows, qui embarquent leur moteur. Kaleido ≥ 1.0 exige Google Chrome. Le rapport reste généré, avec un message à la place du graphique. |
| « ons.dz ne répond pas » | Réseau, proxy ou pare-feu. Le PDF peut être déposé manuellement dans l'étape 1. |
| Certificat SSL d'ons.dz refusé | `ONS_CNT_VERIFY_SSL` (`config/settings.py`) vaut `False` par défaut (chaîne de certificats historiquement incomplète). Repassez-le à `True` dès qu'un téléchargement réussit avec vérification. |
| « database is locked » | Une autre session écrit dans `data/dashboard.db` ; réessayez. L'injection est atomique : la base n'est jamais laissée à moitié modifiée. |
| Fichier Excel ouvert | Fermez le classeur dans Excel avant une saisie ou un recalcul (verrou Windows). |
| Données pas à jour | Les résultats sont mis en cache : menu Streamlit, « Clear cache », ou relancer l'application. Les saisies et injections vident le cache automatiquement. |
| `ModuleNotFoundError: backend` | Le projet n'est pas installé : `pip install -r requirements.txt` (qui contient `-e .`). |

---

## 12. Sources, licences et évolutions

- **Données** : Office National des Statistiques (ONS) ; IPC et comptes
  nationaux trimestriels.
- **Fonds de carte** (`assets/geo/`), générés par
  `scripts/preparer_fonds_de_carte.py` à partir de
  [geoBoundaries](https://www.geoboundaries.org) :
  - frontière nationale et wilaya d'Alger : OpenStreetMap / Wambacher, licence **ODbL 1.0** ;
  - communes d'Alger : OpenStreetMap, licence **CC BY-SA 2.0**.

  Attribution : « © les contributeurs d'OpenStreetMap, via geoBoundaries ».
- **Polices** (`assets/fonts/`) : Montserrat et Inter, licence SIL Open Font
  License 1.1 (textes joints).
- **Pistes d'évolution** :
  - compléter la table de correspondance des postes CNT après ingestion d'un
    premier rapport réel ;
  - repasser la vérification SSL à `True` ;
  - ajouter un triangle de révisions des millésimes CNT ;
  - mettre en place un volet de prévision du PIB.
