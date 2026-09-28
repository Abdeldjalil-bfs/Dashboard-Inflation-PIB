# Déploiement — Tableau de bord Inflation et PIB

Fiche pratique pour mettre l'application en ligne : ce qu'elle attend de
l'environnement d'hébergement, comment la pousser sur **Streamlit Community
Cloud**, et l'alternative auto-hébergée (Docker) recommandée pour un usage en
production. Complète le README (§1 à §3, installation locale) sans le
répéter.

---

## 1. Ce que l'application attend de l'hôte

| Besoin | Détail |
|---|---|
| **Python** | 3.11 ou plus récent (`pyproject.toml` : `requires-python = ">=3.11"`) |
| **Bibliothèques système** | Aucune : pas de GTK/Pango, pas de navigateur headless. `kaleido==0.2.1` (Linux/macOS) ou `0.1.0.post1` (Windows) embarque son propre moteur de rendu PNG ; `reportlab` est 100 % Python |
| **Point d'entrée** | `app/Home.py` (commande : `streamlit run app/Home.py`) |
| **Port** | 8501 par défaut (`.streamlit/config.toml`) |
| **Stockage local en écriture** | `data/`, `outputs/`, `logs/` — voir §3, c'est le point le plus important pour un hébergement cloud |
| **Réseau sortant (facultatif)** | `ons.dz` en HTTPS, uniquement pour la page **Ingestion de données** (PIB). Le reste de l'application ne fait aucun appel réseau |
| **Secrets** | Aucun aujourd'hui : l'authentification est un fichier Excel local (`data/users.xlsx`), pas de clé d'API, pas de `st.secrets` utilisé dans le code |

---

## 2. Dépendances (`requirements.txt`)

| Paquet | Rôle |
|---|---|
| `streamlit==1.64.0` | Interface |
| `pandas==3.0.6`, `numpy==2.4.6` | Calculs |
| `openpyxl==3.1.5` | Lecture/écriture des classeurs Excel (sources et fichiers de calculs) |
| `plotly==5.24.1` | Graphiques |
| `kaleido==0.2.1` *(non Windows)* / `0.1.0.post1` *(Windows)* | Export PNG des graphiques pour les rapports PDF |
| `reportlab==5.0.1` | Génération des rapports PDF |
| `pillow==12.3.0` | Images (logo, PDF) |
| `bcrypt==5.0.0` | **Installé mais plus utilisé** — voir §5, l'authentification a été simplifiée en fichier Excel en clair |
| `pdfplumber==0.11.10` | Extraction des tableaux des PDF CNT (ingestion PIB) |
| `requests==2.33.1`, `urllib3==2.6.3` | Téléchargement des rapports CNT sur ons.dz |
| `-e .` | Installe le projet lui-même (résout `from backend...`, `from config...`) |

`requirements-dev.txt` (pytest, ruff, pymupdf) n'est nécessaire qu'en
développement/CI, jamais en production.

Sur un hôte Linux (Streamlit Community Cloud, Docker, VM), c'est la ligne
`kaleido==0.2.1; platform_system != "Windows"` qui s'installe : aucune action
particulière à prévoir, aucun paquet système supplémentaire (pas de
`packages.txt` à ajouter pour Streamlit Community Cloud).

---

## 3. Le point critique : stockage et persistance

Le projet distingue déjà, dans `.gitignore`, ce qui est **source** (versionné)
de ce qui est **généré** (recréé à l'exécution) :

| Fichier / dossier | Statut Git | Comment il apparaît en déploiement |
|---|---|---|
| `data/raw/inflation/*.xlsx`, `data/raw/pib/*.xlsx` | **Versionné** | Présent dès le clonage, aucune action requise |
| `data/processed/*.xlsx` (fichiers de calculs) | Généré | Se recrée seul au premier accès à une page (pipeline) |
| `data/dashboard.db` (base PIB) | Généré | Se recrée seul à la première ouverture d'une page PIB, à partir des classeurs ONS (« millésime 0 ») |
| `data/users.xlsx` | **Non versionné** | **N'existe pas tant que personne ne le crée** — voir §5, aucune connexion n'est possible sans lui |
| `logs/dashboard.log`, `outputs/*` | Généré | Recréés au fil de l'usage, perdus sans disque persistant |

Ce tableau a une conséquence directe selon l'hébergement choisi :

- **Streamlit Community Cloud** ne garantit pas de disque persistant : le
  système de fichiers de l'app est réinitialisé à chaque redéploiement
  (nouveau commit, redémarrage après mise en veille, changement de
  configuration). Tout ce qui est « Généré » ci-dessus est reconstruit sans
  problème — mais **`data/users.xlsx`, les comptes ajoutés en cours de route,
  les saisies manuelles et l'historique des rapports CNT importés disparaissent
  au prochain redémarrage.** Convient à une démonstration ou un accès interne
  non critique, pas à un usage où les comptes et les saisies doivent durer.
- **Docker auto-hébergé** (§7) résout ce point avec un simple montage de volume
  sur `data/` : c'est l'option recommandée dès que la persistance compte
  réellement (comptes utilisateurs, historique des rapports CNT ingérés,
  saisies manuelles).

Vu la nature de l'application (statistiques de la Banque d'Algérie), l'option
Docker auto-hébergée sur une machine ou un cloud privé est aussi préférable du
point de vue de la maîtrise des données : Streamlit Community Cloud est un
service tiers public.

---

## 4. Le dépôt n'est pas encore un dépôt Git

Étape préalable à toute mise en ligne (Streamlit Community Cloud comme la
plupart des CI/CD Docker) : le projet actuel n'a pas d'historique Git.

```bash
git init
git add .
git commit -m "Version initiale du tableau de bord"
git branch -M main
git remote add origin <url-du-dépôt-github>
git push -u origin main
```

Le `.gitignore` existant exclut déjà correctement les secrets et le contenu
généré (voir §3) : rien à ajuster avant ce premier commit. Vérifiez simplement
qu'aucun fichier `data/users.xlsx` réel (avec de vrais mots de passe) ne
traîne avant le `git add .` — il est exclu par `.gitignore`, mais mieux vaut
s'en assurer une fois (`git status` doit ne pas le lister).

---

## 5. Comptes utilisateurs : ce qui a changé, ce qui est à jour

L'authentification a été simplifiée en cours de projet : fichier Excel en
clair (`username` / `password`), sans distinction de profil — tout compte
authentifié a accès à l'ensemble de l'application
(`app/components/auth.py::est_admin()` renvoie toujours `True`).

**Deux fichiers du dépôt n'ont pas suivi ce changement et ne doivent plus être
utilisés :**

| Fichier | Problème |
|---|---|
| `scripts/creer_utilisateur.py` | Écrit encore au format bcrypt (`password_hash`, `role`) via `backend/auth/users.py` — un compte créé avec ce script **ne pourra pas se connecter** (la page de connexion compare `password` en clair, pas `password_hash`) |
| `scripts/migrer_mots_de_passe.py` | Idem, propre à l'ancien système |

**Façon actuelle, correcte, de créer ou provisionner `data/users.xlsx`** (deux
colonnes `username`, `password`, un compte par ligne) :

```python
import pandas as pd

pd.DataFrame({
    "username": ["mon.identifiant"],
    "password": ["un-mot-de-passe-a-changer"],
}).to_excel("data/users.xlsx", index=False)
```

Ou, pour ajouter un compte à un fichier existant :

```python
import pandas as pd

df = pd.read_excel("data/users.xlsx")
df.loc[len(df)] = ["nouvel.identifiant", "mot-de-passe"]
df.to_excel("data/users.xlsx", index=False)
```

`data/users.example.xlsx` (à jour, colonnes `username`/`password`) sert de
modèle. **Sans `data/users.xlsx`, la page de connexion échoue purement et
simplement** : c'est la première chose à provisionner sur un environnement
neuf, avant tout accès.

---

## 6. Option A — Streamlit Community Cloud

Adapté à une démonstration, un accès interne restreint ou un prototype ; voir
la réserve de persistance du §3 avant de l'utiliser pour un usage durable.

1. **Pousser le dépôt sur GitHub** (§4), en dépôt privé de préférence (aucun
   compte ni mot de passe n'y figure grâce à `.gitignore`, mais les classeurs
   de données économiques restent internes).
2. Sur [share.streamlit.io](https://share.streamlit.io), **New app** → choisir
   le dépôt, la branche (`main`), et le fichier principal : `app/Home.py`.
3. **Version de Python** : sélectionner 3.11 (ou plus récent) dans les
   paramètres avancés du déploiement ; à défaut, un fichier `.python-version`
   à la racine du dépôt contenant `3.11` sert de repli.
4. Laisser Streamlit installer `requirements.txt` (aucun `packages.txt`
   nécessaire, voir §2).
5. **Avant le premier accès**, ou juste après le premier déploiement (le
   système de fichiers est alors disponible le temps que le conteneur tourne) :
   déposer un `data/users.xlsx` valable (§5) — soit en le committant
   temporairement pour le tout premier déploiement (dépôt **privé**
   uniquement, puis changer les mots de passe), soit via un petit script de
   démarrage. Sans quoi personne ne peut se connecter.
6. Ouvrir une page du module PIB une première fois pour laisser
   `data/dashboard.db` se construire à partir des classeurs ONS.
7. Espérer une inactivité prolongée fait mettre l'app en veille : elle
   redémarre au prochain accès, mais **repart alors de zéro** pour tout ce qui
   n'est pas versionné (§3) — pensez à re-déposer `users.xlsx` si besoin.

---

## 7. Option B — Auto-hébergé (Docker), recommandé en production

Le `Dockerfile` du dépôt est déjà prêt :

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8501
CMD ["streamlit", "run", "app/Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

```bash
docker build -t dashboard-bda .
docker run -d --name dashboard-bda \
  -p 8501:8501 \
  -v "$PWD/data:/app/data" \
  -v "$PWD/logs:/app/logs" \
  -v "$PWD/outputs:/app/outputs" \
  --restart unless-stopped \
  dashboard-bda
```

Les trois montages de volume (`data`, `logs`, `outputs`) sont ce qui règle le
problème du §3 : comptes, base PIB, saisies et journaux survivent à un
redémarrage du conteneur.

Avant le tout premier lancement, provisionner `data/users.xlsx` sur l'hôte
(§5) — le volume le rendra visible au conteneur dès le démarrage.

**Pour une mise en production réelle**, ajouter par-dessus :

- un reverse proxy TLS devant le port 8501 (Nginx, Caddy ou Traefik) : le
  serveur Streamlit lui-même ne fait pas de HTTPS ;
- une sauvegarde régulière de `data/` (classeurs sources, `dashboard.db`,
  `users.xlsx`, saisies) — ce sont les seules données qui ne se
  regénèrent pas automatiquement ;
- une supervision de `logs/dashboard.log` (connexions, ingestions, saisies,
  erreurs) déjà produit par l'application.

---

## 8. Autres points à vérifier avant une mise en ligne

- `config/settings.py::ONS_CNT_VERIFY_SSL = False` : la vérification TLS du
  téléchargement des rapports CNT sur ons.dz est désactivée par défaut (chaîne
  de certificats historiquement incomplète côté ons.dz, jamais retestée en
  environnement de déploiement). À repasser à `True` dès qu'un téléchargement
  réussit avec la vérification activée depuis l'environnement cible.
- Le mot de passe stocké dans `data/users.xlsx` est en clair : le fichier ne
  doit jamais se retrouver dans un dépôt public, ni être transmis autrement
  que par un canal déjà sécurisé (`.gitignore` l'exclut déjà du dépôt).
- `bcrypt` reste dans `requirements.txt` bien qu'il ne soit plus utilisé
  (authentification en clair, §5) : sans impact fonctionnel, juste un paquet
  installé pour rien. À retirer si une revue de dépendances est faite un jour.
- Exécuter `pytest` (voir README §10) avant tout déploiement : la suite
  couvre les calculs, l'ingestion CNT, la génération des rapports et les
  pages elles-mêmes.
