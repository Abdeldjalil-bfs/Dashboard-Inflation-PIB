# Audit du volet PIB — état des lieux et décisions de fusion

Audit réalisé avant toute modification (septembre 2026), sur `app/`,
`backend/`, `config/` et `data/`.

## 1. Ce qui existait

| Élément | Emplacement | État |
|---|---|---|
| Lecture des fichiers ONS | `backend/pib/lecture_ons.py` | Fonctionnelle. Correspondance ONS → secteurs **codée en dur** dans le module. Demande : nominal seulement. |
| Calculs | `backend/pib/calculator.py` | Glissements QoQ/YoY, PIB nominal offre/demande, split H/HH, contributions (méthode 1 seule), contrôle d'additivité. |
| Graphiques | `backend/pib/visualizer.py` | 3 figures (`template="plotly_white"`, en conflit avec le thème sombre). |
| Pages | `7_PIB_Vue_Generale.py`, `10_PIB_Secteurs.py`, `8_PIB_Previsions.py` | Vue générale (3 KPI), secteurs (KPI + contributions empilées), prévisions (page vide). |
| Prévision | `backend/pib/forecasting/*` | Fichiers vides. |
| Navigation | `app/components/layout.py` (`PAGES_PIB`) | Vue d'ensemble / Secteurs / Prévisions. |
| Accueil | `app/Home.py` | Carte PIB « Données en attente ». |
| Configuration | `config/pib_config.json`, `config/settings.py` | Libellés des secteurs et postes, chemins. |
| Tests | `tests/test_pib_calculator.py` | Formules sur données synthétiques. |
| Données | `data/raw/pib/PIB_TR_S.xlsx`, `PIB_TR_D.xlsx` | 6 onglets chacun : `PIB_N`, `Tn`, `Tv`, `Def`, `PIB_R`, `PIB_R_SA`. |

## 2. Réutilisable tel quel

- Thème (`app/components/theme.py`, `config/branding.py`), en-tête (`bandeau`),
  navigation latérale générique (`_navigation`), sélecteur de période
  trimestriel (`selecteur_periode_trimestres`), carte KPI, bloc
  « graphique puis tableau + CSV » (`graphique_puis_tableau`).
- Moteur de rapport (`reporting.py`) : chaîne Jinja2 → WeasyPrint → repli
  navigateur, `_constantes_charte`, `qualificatif_variation`.
- Détection d'anomalies (`anomaly_detection.py`) : z-score robuste, niveau +
  variation, comparaison au même mois calendaire (= même trimestre pour des
  dates de fin de trimestre).

## 3. Constats sur les données (vérifiés numériquement)

1. **[Certain] Les volumes réels sont chaînés, pas à prix constants.** Le titre de
   l'onglet `PIB_R` est « Volume des valeurs ajoutées aux prix de l'année
   précédente chaînés », et la somme des branches en volume s'écarte du PIB
   réel publié de 6 % en moyenne (jusqu'à 14 %). Conséquences :
   - `calculer_pib_reel()` (somme des branches) **ne donnait pas** le PIB réel
     ONS : sa croissance était fausse ;
   - `PIB_HH_reel = PIB_reel − Hydrocarbures_reel` n'a pas de sens en volumes
     chaînés (jusqu'à 1,5 pt d'écart sur la croissance hors hydrocarbures) ;
   - la méthode 1 (prix constants) donne un écart moyen de 0,90 pt entre somme
     des contributions et croissance du PIB, contre 0,26 pt pour la méthode 2.
   **→ Méthode 2 (SCN 2008) retenue par détection automatique**, pas par
   hypothèse (voir `detecter_nature_volumes`).
2. **[Certain] L'écart résiduel de la méthode 2 (≈ 0,26 pt en moyenne) est
   structurel.** Les taux de croissance ONS (`Tv`) sont arrondis à 0,1 pt et
   le chaînage n'est pas additif. Avec une tolérance de ±0,1 pt, environ 70 %
   des trimestres déclenchent la note technique. C'est attendu : le waterfall
   affiche une barre « Écart de chaînage » pour que le total reboucle
   exactement sur la croissance publiée.
3. **[Certain] La variation de stocks en volume (`PIB_TR_D`, `PIB_R`) est
   inexploitable** : elle répète les quatre valeurs de 2001 chaque année. La
   ligne résiduelle « Variations de stocks et écart statistique » est donc
   indispensable.
4. **[Certain] Le PIB réel de l'offre s'arrête à T2 2025**, celui de la demande
   à T4 2025 (valeurs identiques sur la période commune). Le nominal va
   jusqu'à T4 2025 dans les deux fichiers.
5. **[Certain] Les classeurs ONS sont pilotés par formules** (dates en
   `=EDATE`, `PIB_R` recalculé depuis `Tv`). Les réenregistrer avec openpyxl
   efface les valeurs en cache : le fichier deviendrait illisible pour le
   tableau de bord jusqu'à sa réouverture dans Excel. La saisie PIB ne
   réécrit donc **jamais** ces classeurs (voir § 4).

## 4. Décisions de fusion

| Besoin | Décision |
|---|---|
| Calculs | `backend/pib/calculator.py` **adapté** (pas de `calculator_pib.py`) : fonctions existantes conservées, corrigées pour les volumes chaînés ; ajout du déflateur, des deux méthodes de contribution, de l'optique demande, des ratios et du fichier miroir `data/processed/Fichier_PIB_et_calculs.xlsx`. |
| Lecture | `lecture_ons.py` **adapté** : correspondance, feuilles et ligne d'en-tête déplacées dans `config/pib_config.json` ; lecture du PIB total publié et du réel de la demande ; application du journal de saisie. |
| Statistiques | Nouveau `backend/common/statistiques.py` (moyenne, écart-type, moyenne depuis T1, top contributeurs) sur des séries. `identifier_top_contributeurs` de l'inflation y délègue le classement. |
| Graphiques | `backend/pib/visualizer.py` **réécrit** : plus de `plotly_white`, titres toujours renseignés, `export_png`. |
| Page 1 | `7_PIB_Vue_Generale.py` adaptée (4 KPI, graphiques 1 et 2). |
| Page 2 | `10_PIB_Secteurs.py` renommée `10_PIB_Offre.py` et adaptée. |
| Page 3 | Nouvelle `11_PIB_Demande.py`. |
| Rapport | `reporting.py` étendu (`generer_rapport_pib_pdf`), gabarit `rapport_pib.html` partageant `rapport.css` ; nouvelle page `12_PIB_Rapport.py`. |
| Saisie | Page `5_Insertion_Donnees.py` étendue (choix Inflation / PIB). Les saisies PIB vont dans un **journal** `data/raw/pib/PIB_saisies.xlsx`, appliqué à la lecture. Les fichiers ONS restent intacts. |
| Anomalies | `anomaly_detection.py` généralisé (taille de fenêtre paramétrable) ; fenêtre trimestrielle dans `anomaly_rules.json`. |
| Prévisions | Page conservée mais retirée de la navigation : son backend est vide. |
| Graphique 2 | Barres nominal / réel en **taux de croissance**, pas en niveaux : en volumes chaînés, un niveau réel hors hydrocarbures n'existe pas proprement, et comparer un niveau nominal 2025 à un volume en prix chaînés de 2001 n'a pas de lecture économique. L'écart entre les deux barres est l'inflation implicite. |
| Ratios | Taux d'investissement et d'ouverture calculés **en nominal** (convention usuelle ; les volumes chaînés ne se divisent pas entre eux). |
