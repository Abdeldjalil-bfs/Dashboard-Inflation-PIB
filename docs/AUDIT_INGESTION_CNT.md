# Audit préalable — page « Ingestion de données » (CNT ONS)

## 1. Ce qui est réutilisé tel quel

| Élément | Emplacement | Usage dans la page |
|---|---|---|
| Charte, cartes, titres de section, boutons | `app/components/theme.py` | Toute la mise en page (`entete_page`, `titre_section`, `separateur_dore`, `.ba-card`, `.ba-kpi`). |
| En-tête et navigation latérale | `app/components/layout.py` (`bandeau`, `_navigation`) | Nouvelle entrée `PAGES_PIB`, après les pages d'analyse. |
| Cartes KPI | `app/components/kpi_card.py` | Cartes de synthèse de la comparaison (étape 4). |
| Note discrète | `app/components/donnees_pib.note_technique` | Messages d'aide contextuels. |
| Pattern de confirmation | `5_Insertion_Donnees.py` / `saisie_pib.py` | Case « Je confirme… » puis bouton désactivé tant qu'elle n'est pas cochée. |
| Convention de nommage | `app/pages/<n>_PIB_<Nom>.py` | `13_PIB_Ingestion.py`. |
| Chemins | `config/settings.py` | `CNT_DB_PATH`, `ONS_CNT_VERIFY_SSL`, `ONS_CNT_URL_TEMPLATE`. |

## 2. Écarts constatés dans `ons_cnt.py` (avant toute modification)

1. **[Certain] Injection non atomique.** `DataFrame.to_sql` valide sa propre
   transaction sur une connexion `sqlite3`. Test reproduit : `DELETE`, puis
   `to_sql`, puis une panne avant l'écriture dans `cnt_imports`. Résultat :
   l'ancien millésime est supprimé, le nouveau est écrit, et `cnt_imports`
   n'est pas mis à jour. Corrigé par une insertion `executemany` dans un
   seul bloc `with conn:`.
2. **[Certain] `to_excel(xw, "Feuille")` ne fonctionne plus.** Avec pandas
   3.0.6 (installé ici), le nom de feuille passé en position lève
   `IndexError: At least one sheet must be visible`. Ce n'est pas une
   simple dépréciation : l'Excel ne se construisait pas.
3. **[Certain] `urllib3.disable_warnings` est appelé à l'import**, pour tout
   le processus Streamlit. Il n'est désormais appelé que si la vérification
   SSL est désactivée.
4. Chemin de base `"dashboard.db"` et `VERIFY_SSL` codés en dur : déplacés
   dans `config/settings.py`.
5. Erreurs réseau (`ConnectionError`, `Timeout`, `SSLError`) : elles
   remontaient brutes. Elles sont désormais converties en `ONSInjoignable`,
   pour un message clair dans la page. `CNTIntrouvable` est inchangée.
6. `comparer_avec_base` et le contrôle « dernier trimestre » plantent sur un
   tidy sans trimestre (`max()` d'une série vide). Garde ajoutée.

La logique d'extraction (regex, lecture des tableaux, format tidy,
contrôles) n'est **pas** modifiée.

## 3. Écarts avec l'environnement et le cahier des charges

- **[Certain] `www.ons.dz` est refusé par la politique réseau** de
  l'environnement où ce code a été développé (proxy : `CONNECT 403`). Le
  test réel sur `CNT2T2025.pdf`, et donc le test `VERIFY_SSL=True`, n'ont
  **pas pu être exécutés**. Le parcours a été validé sur un PDF de synthèse
  reproduisant les titres et la mise en forme attendus par les regex. Cela
  prouve la tuyauterie, pas l'adéquation aux vrais PDF ONS.
- **[Certain] Les pages d'analyse PIB ne lisent pas la base.** Elles lisent
  `PIB_TR_S.xlsx` / `PIB_TR_D.xlsx` via `pipeline_pib()`. Vider les caches
  après injection ne change donc rien aux graphiques tant que la
  réconciliation (§ 4) n'est pas faite.
- **Profils utilisateurs** : `data/users.xlsx` n'a pas de colonne de rôle.
  La restriction de l'injection passe par une liste optionnelle
  `INGESTION_ADMINS` dans `settings.py` (vide = tout utilisateur connecté).

## 4. Réconciliation CNT ↔ pages d'analyse (proposition, non implémentée)

Les CNT fournissent des **valeurs nominales** et des **taux t/t−4 en prix
chaînés**, sans volumes en niveau. Or les fichiers `PIB_R` de l'ONS sont
eux-mêmes construits par formule à partir de ces taux :
`PIB_R(t) = PIB_R(t−4) × (1 + g(t))`. Proposition :

1. Garder les classeurs ONS comme **socle historique** (2001 →), et lire
   `cnt_pib_derniere` pour **prolonger et réviser** les derniers trimestres :
   - nominal : remplacé par les valeurs CNT ;
   - réel : reconstruit par chaînage des taux CNT sur l'ancrage t−4 du socle.
2. Contributions : la méthode 2 (part nominale t−4 × croissance chaînée),
   déjà en place, ne consomme que des nominaux et des taux. Elle s'applique
   sans changement.
3. Ce que les CNT seuls ne permettent pas : glissement trimestriel (t/t−1)
   en volume et niveau du déflateur. Ils restent dérivés du socle chaîné.
4. Prérequis : une table de correspondance « poste CNT → clé canonique »
   dans `pib_config.json`, établie sur un vrai PDF. Elle est impossible à
   écrire ici tant qu'`ons.dz` est injoignable.

### Avis du conseil (5 perspectives indépendantes + revue croisée)

- Option A rejetée à l'unanimité ; C est l'étape 0 de B.
- Architecture recommandée : charger les classeurs ONS dans `cnt_pib` comme
  un **millésime 0 daté**. `cnt_pib_derniere` produit alors l'hybride sans
  code de fusion ; volumes en niveau et déflateur deviennent une vue calculée.
- Ingérer dès maintenant, **n'afficher** qu'après validation du mapping sur
  un vrai PDF (poste non mappé = échec de l'ingestion).
- Risque sous-estimé : le chaînage t/t−4 forme **quatre chaînes
  indépendantes** (T1, T2, T3, T4). Leurs erreurs d'arrondi divergent et
  créent une saisonnalité artificielle dans le QoQ. Mesurer cette dérive sur
  un recouvrement ; au-delà du signal, afficher « n.d. ».
- À ajouter avant bascule : contrôle des identités comptables à chaque
  ingestion (somme des emplois = PIB), empreinte du PDF et version du
  parseur par millésime, détection d'un changement d'année de base,
  mention « estimation interne » sur les chiffres reconstruits, responsable
  des données nommé, période de comparaison côte à côte.
