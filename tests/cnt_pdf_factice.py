"""
PDF factice au format des rapports CNT de l'ONS, pour tester le parcours
d'ingestion sans réseau. Reproduit ce que les regex d'ons_cnt attendent :
titre de tableau, ligne d'années, ligne « T1 … année … », lignes
« Libellé 1 234,5 … » à virgule décimale et espace des milliers.

Il valide la tuyauterie (extraction -> tidy -> contrôles -> base), PAS
l'adéquation aux vrais PDF de l'ONS.
"""

import io

TITRES = {
    "Valeurs": "Produit Intérieur Brut trimestriel aux prix courants (Millions DA)",
    "Croissance": "Taux de croissance des valeurs ajoutées aux prix de l'année précédente chaînés (%)",
    "Emplois_valeurs": "Equilibre Ressources-Emplois aux prix courants (Millions DA)",
    "Emplois_croissance": "Taux de croissance aux prix de l'année précédente chaînés (%)",
}
POSTES = {
    "Valeurs": ["Agriculture", "Hydrocarbures", "Industrie", "Produit Intérieur Brut"],
    "Croissance": ["Agriculture", "Hydrocarbures", "Industrie", "Produit Intérieur Brut"],
    "Emplois_valeurs": ["Consommation finale", "FBCF", "Exportations", "Importations"],
    "Emplois_croissance": ["Consommation finale", "FBCF", "Exportations", "Importations"],
}


def _nombre(x):
    entier, dec = ("%.1f" % abs(x)).split(".")
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    groupes.insert(0, entier)
    return ("-" if x < 0 else "") + " ".join(groupes) + "," + dec


def lignes_tableau(bloc, annee, trimestre, revision=0.0):
    annees = [annee - 2, annee - 1, annee]
    entetes = []
    for a in annees:
        n = 4 if a < annee else trimestre
        entetes += ["T%d" % t for t in range(1, n + 1)] + (["année"] if n == 4 else [])
    lignes = [TITRES[bloc], " ".join(str(a) for a in annees), " ".join(entetes)]
    croissance = "croissance" in bloc.lower()
    for i, poste in enumerate(POSTES[bloc]):
        valeurs = []
        for a in annees:
            n = 4 if a < annee else trimestre
            trims = []
            for t in range(1, n + 1):
                if croissance:
                    v = 1.5 + i - 0.3 * t + 0.1 * (a - annee)
                else:
                    v = 100000.0 * (i + 1) + 1000.0 * t + 5000.0 * (a - annee + 2)
                if a == annee - 1 and t == 4:
                    v += revision
                trims.append(round(v, 1))
            valeurs += trims
            if n == 4:
                valeurs.append(round(sum(trims), 1) if not croissance else round(sum(trims) / 4, 1))
        lignes.append(poste + " " + " ".join(_nombre(v) for v in valeurs))
    return lignes


def pdf_cnt(annee=2025, trimestre=2, revision=0.0, blocs=None) -> bytes:
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    c = canvas.Canvas(tampon, pagesize=landscape(A4))
    for page, bloc in enumerate(blocs or TITRES, start=1):
        y = 540
        for ligne in lignes_tableau(bloc, annee, trimestre, revision):
            c.setFont("Helvetica", 7)
            c.drawString(20, y, ligne)
            y -= 14
        c.drawString(400, 20, str(page))
        c.showPage()
    c.save()
    return tampon.getvalue()
