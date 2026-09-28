"""
Création ou mise à jour d'un compte :

    python scripts/creer_utilisateur.py IDENTIFIANT [admin|lecteur]

Le mot de passe est demandé sans écho et stocké haché (bcrypt).
"""

import getpass
import sys

from backend.auth.users import ajouter

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    identifiant = sys.argv[1]
    role = sys.argv[2] if len(sys.argv) > 2 else "lecteur"
    mot_de_passe = getpass.getpass("Mot de passe pour %s : " % identifiant)
    if mot_de_passe != getpass.getpass("Confirmation : "):
        sys.exit("Les deux saisies diffèrent.")
    ajouter(identifiant, mot_de_passe, role)
    print("Compte « %s » enregistré (profil %s)." % (identifiant, role))
