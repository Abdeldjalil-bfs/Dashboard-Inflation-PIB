"""
Comptes utilisateurs : vérification des mots de passe par hachage bcrypt et
profils (admin / lecteur).

Fichier `data/users.xlsx` (hors dépôt Git), colonnes :
    username       identifiant
    password_hash  empreinte bcrypt (produite par scripts/migrer_mots_de_passe.py
                   ou scripts/creer_utilisateur.py)
    role           « admin » ou « lecteur » (colonne facultative : absente,
                   tout le monde est admin, comme avant la migration)

Compatibilité : un ancien fichier portant encore une colonne `password` en
clair reste utilisable, le temps de lancer le script de migration ; chaque
connexion par mot de passe en clair est alors signalée dans le journal.
"""

import os

import bcrypt
import pandas as pd

ROLES = ("admin", "lecteur")
ROLE_PAR_DEFAUT = "admin"
COLONNES = ["username", "password_hash", "role"]


def hacher(mot_de_passe: str) -> str:
    return bcrypt.hashpw(str(mot_de_passe).encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def _est_hash(valeur) -> bool:
    return isinstance(valeur, str) and valeur.startswith(("$2a$", "$2b$", "$2y$"))


def charger(chemin=None) -> pd.DataFrame:
    """Table des comptes (vide si le fichier est absent)."""
    from config.settings import USERS_FILE

    chemin = str(chemin or USERS_FILE)
    if not os.path.exists(chemin):
        return pd.DataFrame(columns=COLONNES)
    df = pd.read_excel(chemin, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    if "role" not in df.columns:
        df["role"] = ROLE_PAR_DEFAUT
    df["role"] = df["role"].fillna(ROLE_PAR_DEFAUT).str.strip().str.lower()
    return df


def verifier(identifiant: str, mot_de_passe: str, chemin=None):
    """
    Renvoie {"username", "role", "hache"} si les identifiants sont valides,
    None sinon. Comparaison bcrypt (temps constant) ; repli sur l'ancien
    format en clair tant que la migration n'a pas été faite.
    """
    if not identifiant or not mot_de_passe:
        return None
    df = charger(chemin)
    lignes = df[df["username"].astype(str).str.strip() == str(identifiant).strip()]
    if lignes.empty:
        return None
    ligne = lignes.iloc[0]
    empreinte = ligne.get("password_hash")
    if _est_hash(empreinte):
        valide = bcrypt.checkpw(str(mot_de_passe).encode("utf-8"), empreinte.encode("ascii"))
        hache = True
    else:
        clair = ligne.get("password")
        valide = clair is not None and not pd.isna(clair) and str(clair) == str(mot_de_passe)
        hache = False
    if not valide:
        return None
    role = ligne.get("role") if ligne.get("role") in ROLES else ROLE_PAR_DEFAUT
    return {"username": str(ligne["username"]).strip(), "role": role, "hache": hache}


def migrer(chemin=None, role_par_defaut: str = ROLE_PAR_DEFAUT) -> int:
    """
    Remplace les mots de passe en clair par leur empreinte bcrypt et ajoute
    la colonne role. Idempotent (les empreintes existantes sont conservées).
    Renvoie le nombre de comptes hachés.
    """
    from config.settings import USERS_FILE

    chemin = str(chemin or USERS_FILE)
    df = charger(chemin)
    if "password_hash" not in df.columns:
        df["password_hash"] = None
    n = 0
    for i, ligne in df.iterrows():
        if _est_hash(ligne.get("password_hash")):
            continue
        clair = ligne.get("password")
        if clair is None or pd.isna(clair) or str(clair) == "":
            continue
        df.at[i, "password_hash"] = hacher(clair)
        n += 1
    df["role"] = df["role"].where(df["role"].isin(ROLES), role_par_defaut)
    df[COLONNES].to_excel(chemin, index=False)
    return n


def ajouter(identifiant: str, mot_de_passe: str, role: str = "lecteur", chemin=None) -> None:
    """Crée ou met à jour un compte (mot de passe haché)."""
    from config.settings import USERS_FILE

    if role not in ROLES:
        raise ValueError("Rôle inconnu : %s (attendu : %s)" % (role, ", ".join(ROLES)))
    chemin = str(chemin or USERS_FILE)
    df = charger(chemin)
    if "password_hash" not in df.columns:
        df["password_hash"] = None
    df = df[df["username"] != identifiant]
    df = pd.concat(
        [df, pd.DataFrame([{"username": identifiant, "password_hash": hacher(mot_de_passe), "role": role}])],
        ignore_index=True,
    )
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    df[COLONNES].to_excel(chemin, index=False)
