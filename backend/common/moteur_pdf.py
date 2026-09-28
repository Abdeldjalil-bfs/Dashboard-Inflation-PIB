"""
Moteur de rendu PDF, 100 % Python (ReportLab) : aucune bibliothèque système
(GTK, Pango, navigateur) n'est requise, le rapport se génère sur un poste
Windows standard.

Ce module n'est importé QUE par backend/inflation/reporting.py, qui expose
l'interface unique `rendre_document()`. Il consomme un document neutre
(dictionnaire) décrit ci-dessous et ne connaît ni l'inflation ni le PIB :
changer de moteur ne touche qu'à ce fichier.

Document :
    {
      "titre_document": "Rapport mensuel d'inflation",   # pied de page
      "couverture": {"titre", "periode", "chiffres": [(libellé, valeur, delta, classe)], "pied"},
      "sections": [{"titre", "chapeau", "blocs": [bloc, ...]}],
      "tracabilite": [(clé, valeur), ...],
    }
Blocs : ("titre_bloc", texte) | ("paragraphe", texte) | ("note", texte)
        | ("avertissement", texte) | ("indicateurs", [(libellé, valeur, delta, classe)])
        | ("figure", chemin_png_ou_None, légende) | ("tableau", [(terme, définition)])
        | ("saut_de_page",)
`classe` : "favorable" (vert), "defavorable" (rouge) ou None.
"""

import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

LARGEUR, HAUTEUR = A4
MARGE = 16 * mm


def _polices(dossier_polices):
    """Enregistre Montserrat (titres) et Inter (texte) ; repli sur Helvetica."""
    noms = {
        "titre": "Helvetica-Bold",
        "titre_moyen": "Helvetica-Bold",
        "texte": "Helvetica",
        "texte_gras": "Helvetica-Bold",
        "texte_moyen": "Helvetica-Bold",
    }
    fichiers = {
        "Montserrat-Bold": "titre",
        "Montserrat-SemiBold": "titre_moyen",
        "Inter-Regular": "texte",
        "Inter-Bold": "texte_gras",
        "Inter-SemiBold": "texte_moyen",
    }
    for fichier, role in fichiers.items():
        chemin = os.path.join(str(dossier_polices), fichier + ".ttf")
        if os.path.exists(chemin):
            if fichier not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(fichier, chemin))
            noms[role] = fichier
    return noms


class _Rendu:
    def __init__(self, charte, dossier_polices, logo):
        self.c = {k: colors.HexColor(v) for k, v in charte.items() if str(v).startswith("#")}
        self.police = _polices(dossier_polices)
        self.logo = logo
        self.institution = charte.get("institution", "")
        self.total = "?"
        p = self.police
        self.styles = {
            "section": ParagraphStyle(
                "section", fontName=p["titre"], fontSize=15, leading=19, textColor=self.c["navy"], spaceAfter=3 * mm
            ),
            "chapeau": ParagraphStyle(
                "chapeau",
                fontName=p["texte"],
                fontSize=9.5,
                leading=13.5,
                textColor=self.c["encre_attenuee"],
                spaceAfter=4 * mm,
            ),
            "titre_bloc": ParagraphStyle(
                "titre_bloc",
                fontName=p["titre_moyen"],
                fontSize=8.5,
                leading=11,
                textColor=self.c["or_fonce"],
                spaceBefore=3 * mm,
                spaceAfter=1.5 * mm,
            ),
            "paragraphe": ParagraphStyle(
                "paragraphe",
                fontName=p["texte"],
                fontSize=9.5,
                leading=14,
                textColor=self.c["encre"],
                spaceAfter=2.5 * mm,
                alignment=TA_LEFT,
            ),
            "note": ParagraphStyle(
                "note",
                fontName=p["texte"],
                fontSize=8,
                leading=11,
                textColor=self.c["encre_attenuee"],
                leftIndent=3 * mm,
                borderPadding=(2 * mm, 2 * mm, 2 * mm, 2 * mm),
                spaceBefore=1 * mm,
                spaceAfter=3 * mm,
                backColor=self.c["papier_alt"],
            ),
            "legende": ParagraphStyle(
                "legende",
                fontName=p["texte"],
                fontSize=7.5,
                leading=10,
                textColor=self.c["encre_attenuee"],
                spaceAfter=3 * mm,
            ),
            "cellule": ParagraphStyle(
                "cellule", fontName=p["texte"], fontSize=8.5, leading=11.5, textColor=self.c["encre"]
            ),
            "terme": ParagraphStyle(
                "terme", fontName=p["texte_moyen"], fontSize=8.5, leading=11.5, textColor=self.c["navy"]
            ),
            "ind_lib": ParagraphStyle(
                "ind_lib", fontName=p["texte_moyen"], fontSize=6.5, leading=8.5, textColor=self.c["encre_attenuee"]
            ),
            "ind_val": ParagraphStyle(
                "ind_val", fontName=p["titre"], fontSize=15, leading=18, textColor=self.c["navy"]
            ),
            "ind_delta": ParagraphStyle("ind_delta", fontName=p["texte_moyen"], fontSize=8, leading=10),
        }

    # ------------------------------------------------------------ couleurs
    def _couleur_classe(self, classe):
        return {"favorable": self.c["positif"], "defavorable": self.c["negatif"]}.get(classe, self.c["encre_attenuee"])

    # ------------------------------------------------------------ pages
    def _fond_couverture(self, canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(self.c["navy"])
        canvas.rect(0, 0, LARGEUR, HAUTEUR, stroke=0, fill=1)
        if self.logo and os.path.exists(self.logo):
            canvas.drawImage(
                self.logo,
                MARGE + 4 * mm,
                HAUTEUR - 62 * mm,
                width=62 * mm,
                height=26 * mm,
                preserveAspectRatio=True,
                mask="auto",
                anchor="sw",
            )
        canvas.setStrokeColor(self.c["or"])
        canvas.setLineWidth(1.2)
        canvas.line(MARGE + 4 * mm, HAUTEUR - 80 * mm, MARGE + 60 * mm, HAUTEUR - 80 * mm)
        canvas.restoreState()

    def _cadre_page(self, titre_document, tracabilite):
        def dessiner(canvas, doc):
            canvas.saveState()
            canvas.setFont(self.police["titre_moyen"], 7)
            canvas.setFillColor(self.c["or_fonce"])
            canvas.drawString(MARGE, HAUTEUR - 11 * mm, self.institution.upper())
            canvas.setStrokeColor(self.c["or"])
            canvas.setLineWidth(0.4)
            canvas.line(MARGE, HAUTEUR - 12.5 * mm, LARGEUR - MARGE, HAUTEUR - 12.5 * mm)
            canvas.setFont(self.police["texte"], 7)
            canvas.setFillColor(self.c["encre_attenuee"])
            canvas.drawString(MARGE, 9 * mm, titre_document + " — " + tracabilite)
            canvas.drawRightString(LARGEUR - MARGE, 9 * mm, "page %d / %s" % (doc.page, self.total))
            canvas.restoreState()

        return dessiner

    # ------------------------------------------------------------ blocs
    def _p(self, texte, style):
        return Paragraph(escape(str(texte)).replace("\n", "<br/>"), self.styles[style])

    def _indicateurs(self, liste):
        cellules = []
        for libelle, valeur, delta, classe in liste:
            contenu = [self._p(str(libelle).upper(), "ind_lib"), self._p(valeur, "ind_val")]
            if delta:
                style = ParagraphStyle("d", parent=self.styles["ind_delta"], textColor=self._couleur_classe(classe))
                contenu.append(Paragraph(escape(delta), style))
            cellules.append(contenu)
        largeur = (LARGEUR - 2 * MARGE) / max(len(cellules), 1)
        table = Table([cellules], colWidths=[largeur] * len(cellules))
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), self.c["papier_alt"]),
                    # Un simple LINEABOVE se voyait sur le fond sombre de la
                    # couverture mais se perdait sur une page blanche (le
                    # fond 'papier_alt' est presque blanc) : bordure pleine
                    # + séparateurs internes, en or, visibles sur les deux fonds.
                    ("BOX", (0, 0), (-1, -1), 0.75, self.c["or"]),
                    ("INNERGRID", (0, 0), (-1, -1), 0.6, self.c["or"]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3.5 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                ]
            )
        )
        return [table, Spacer(1, 4 * mm)]

    def _figure(self, chemin, legende):
        largeur = LARGEUR - 2 * MARGE
        if chemin and os.path.exists(chemin):
            image = Image(chemin)
            ratio = image.imageHeight / float(image.imageWidth)
            image.drawWidth, image.drawHeight = largeur, largeur * ratio
            return [KeepTogether([image, self._p(legende, "legende")])]
        # Export d'image indisponible : le rapport se génère quand même.
        cadre = Table(
            [
                [
                    self._p(
                        "Graphique indisponible : l'export d'image a échoué sur ce poste "
                        "(voir le README, section Dépannage). " + legende,
                        "note",
                    )
                ]
            ],
            colWidths=[largeur],
        )
        cadre.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, self.c["encre_attenuee"])]))
        return [cadre, Spacer(1, 3 * mm)]

    def _tableau(self, lignes):
        data = [[self._p(a, "terme"), self._p(b, "cellule")] for a, b in lignes]
        table = Table(data, colWidths=[48 * mm, LARGEUR - 2 * MARGE - 48 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.3, self.c["papier_alt"]),
                    ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ]
            )
        )
        return [table, Spacer(1, 3 * mm)]

    def bloc(self, bloc):
        genre = bloc[0]
        if genre in ("titre_bloc", "paragraphe", "note"):
            texte = bloc[1]
            if not texte:
                return []
            return [self._p(texte.upper() if genre == "titre_bloc" else texte, genre)]
        if genre == "avertissement":
            return [Spacer(1, 3 * mm), self._p(bloc[1], "note")]
        if genre == "indicateurs":
            return self._indicateurs(bloc[1])
        if genre == "figure":
            return self._figure(bloc[1], bloc[2])
        if genre == "tableau":
            return self._tableau(bloc[1]) if bloc[1] else []
        if genre == "saut_de_page":
            return [PageBreak()]
        raise ValueError("Bloc inconnu : %s" % genre)

    # ------------------------------------------------------------ couverture
    def couverture(self, cv):
        blanc = colors.white
        titre = ParagraphStyle("ct", fontName=self.police["titre"], fontSize=28, leading=34, textColor=blanc)
        periode = ParagraphStyle(
            "cp", fontName=self.police["titre_moyen"], fontSize=15, leading=20, textColor=self.c["or"]
        )
        inst = ParagraphStyle("ci", fontName=self.police["titre_moyen"], fontSize=9, leading=12, textColor=self.c["or"])
        pied = ParagraphStyle(
            "cpi", fontName=self.police["texte"], fontSize=8, leading=11, textColor=colors.HexColor("#9FB3C2")
        )
        elements = [
            Spacer(1, 76 * mm),
            Paragraph(escape(self.institution.upper()), inst),
            Spacer(1, 10 * mm),
            Paragraph(escape(cv["titre"]).replace("\n", "<br/>"), titre),
            Spacer(1, 5 * mm),
            Paragraph(escape(cv["periode"]), periode),
            Spacer(1, 22 * mm),
        ]
        cellules = []
        for libelle, valeur, delta, classe in cv.get("chiffres", []):
            lib = ParagraphStyle(
                "l", fontName=self.police["texte_moyen"], fontSize=7, textColor=colors.HexColor("#9FB3C2")
            )
            val = ParagraphStyle("v", fontName=self.police["titre"], fontSize=20, leading=24, textColor=self.c["or"])
            contenu = [Paragraph(escape(libelle.upper()), lib), Spacer(1, 2 * mm), Paragraph(escape(valeur), val)]
            if delta:
                dl = ParagraphStyle(
                    "d", fontName=self.police["texte_moyen"], fontSize=8.5, textColor=self._couleur_classe(classe)
                )
                contenu.append(Paragraph(escape(delta), dl))
            cellules.append(contenu)
        if cellules:
            table = Table([cellules], colWidths=[(LARGEUR - 2 * MARGE - 8 * mm) / len(cellules)] * len(cellules))
            table.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.6, self.c["or_fonce"]),
                        ("INNERGRID", (0, 0), (-1, -1), 0.6, self.c["or_fonce"]),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                        ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
                    ]
                )
            )
            elements.append(table)
        elements += [Spacer(1, 40 * mm), Paragraph(escape(cv.get("pied", "")), pied)]
        return elements


def rendre(document, chemin_sortie, charte, dossier_polices, logo=None):
    """Produit le PDF ; renvoie le nombre de pages écrites."""
    rendu = _Rendu(charte, dossier_polices, logo)
    trace = " · ".join(v for _k, v in document.get("tracabilite", [])[:2])

    def construire():
        doc = BaseDocTemplate(
            chemin_sortie, pagesize=A4, title=document["titre_document"], author=charte.get("institution", "")
        )
        cadre = Frame(MARGE, 16 * mm, LARGEUR - 2 * MARGE, HAUTEUR - 34 * mm, id="corps")
        cadre_cv = Frame(MARGE + 4 * mm, 20 * mm, LARGEUR - 2 * MARGE - 8 * mm, HAUTEUR - 30 * mm, id="cv")
        doc.addPageTemplates(
            [
                PageTemplate(id="couverture", frames=[cadre_cv], onPage=rendu._fond_couverture),
                PageTemplate(id="corps", frames=[cadre], onPage=rendu._cadre_page(document["titre_document"], trace)),
            ]
        )
        histoire = rendu.couverture(document["couverture"]) + [NextPageTemplate("corps"), PageBreak()]
        for rang, section in enumerate(document["sections"]):
            if rang:
                histoire.append(PageBreak())
            histoire.append(Paragraph(escape(section["titre"]), rendu.styles["section"]))
            if section.get("chapeau"):
                histoire.append(rendu._p(section["chapeau"], "chapeau"))
            for bloc in section["blocs"]:
                histoire += rendu.bloc(bloc)
        if document.get("tracabilite"):
            histoire += [Spacer(1, 6 * mm)] + rendu._tableau(document["tracabilite"])
        doc.build(histoire)
        return doc.page

    # Deux passes : la première compte les pages, la seconde écrit « page x / N ».
    rendu.total = construire()
    return construire()
