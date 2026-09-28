"""
Migration des mots de passe de data/users.xlsx vers bcrypt.

    python scripts/migrer_mots_de_passe.py

Remplace chaque mot de passe en clair par son empreinte bcrypt, supprime la
colonne en clair et ajoute la colonne « role » (admin par défaut pour les
comptes existants). Faites une copie de sauvegarde du fichier avant.
"""

from backend.auth.users import migrer

if __name__ == "__main__":
    print("%d compte(s) haché(s)." % migrer())
