"""
Prépare les fonds de carte embarqués dans assets/geo/ à partir des fichiers
geoBoundaries (https://www.geoboundaries.org), version « simplified » :

    python scripts/preparer_fonds_de_carte.py ADM0.geojson ADM1.geojson ADM3.geojson

  - algerie.geojson        : frontière nationale (ADM0, licence ODbL 1.0) ;
  - alger_wilaya.geojson   : limite de la wilaya d'Alger (ADM1, ODbL 1.0) ;
  - alger_communes.geojson : communes dont le centre tombe dans la wilaya
                             (ADM3, CC BY-SA 2.0, dérivé d'OpenStreetMap).

Simplification Douglas-Peucker et arrondi des coordonnées pour garder des
fichiers légers. À n'exécuter que pour régénérer les fonds : l'application
lit les fichiers déjà produits, sans aucun accès réseau.
"""

import json
import sys
from pathlib import Path

SORTIE = Path(__file__).resolve().parent.parent / "assets" / "geo"

# Noms usuels en français des communes que la source transcrit en anglais.
NOMS_FRANCAIS = {
    "Central Algiers": "Alger-Centre", "Bab Al Wadi": "Bab El Oued", "Burj Al Kifan": "Bordj El Kiffan",
    "Bulughin": "Bologhine", "Al Muhammadiyya": "Mohammadia", "Eucalyptus": "Les Eucalyptus",
    "Maalma": "Mahelma", "Djasr Kasentina": "Djasr Kasentina", "Casbah": "Casbah",
    "Hussein Dey": "Hussein Dey", "Cheraga": "Chéraga", "Staoueli": "Staouéli",
    "Rais Hamidou": "Raïs Hamidou", "Bir Mourad Rais": "Bir Mourad Raïs",
}


def _dist(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** 0.5


def simplifier(points, tol):
    """Douglas-Peucker itératif (pas de récursion profonde)."""
    if len(points) < 5:
        return points
    garder = [False] * len(points)
    garder[0] = garder[-1] = True
    pile = [(0, len(points) - 1)]
    while pile:
        i, j = pile.pop()
        dmax, k = 0, None
        for m in range(i + 1, j):
            d = _dist(points[m], points[i], points[j])
            if d > dmax:
                dmax, k = d, m
        if k is not None and dmax > tol:
            garder[k] = True
            pile += [(i, k), (k, j)]
    res = [p for p, g in zip(points, garder) if g]
    return res if len(res) >= 4 else points


def _polygones(geometrie):
    if geometrie["type"] == "Polygon":
        return [geometrie["coordinates"]]
    return geometrie["coordinates"]


def alleger(geometrie, tol, decimales=4):
    polys = []
    for poly in _polygones(geometrie):
        anneaux = [[[round(x, decimales), round(y, decimales)] for x, y in simplifier(a, tol)] for a in poly]
        polys.append(anneaux)
    return {"type": "MultiPolygon", "coordinates": polys}


def dans_polygone(x, y, anneau):
    dedans = False
    for (x1, y1), (x2, y2) in zip(anneau, anneau[1:] + anneau[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dedans = not dedans
    return dedans


def centre(geometrie):
    anneau = max((p[0] for p in _polygones(geometrie)), key=len)
    xs, ys = [p[0] for p in anneau], [p[1] for p in anneau]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def ecrire(nom, features, source, licence):
    SORTIE.mkdir(parents=True, exist_ok=True)
    doc = {"type": "FeatureCollection", "source": source, "licence": licence, "features": features}
    chemin = SORTIE / nom
    chemin.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(nom, len(features), "entités", chemin.stat().st_size // 1024, "Ko")


def main(adm0, adm1, adm3):
    pays = json.loads(Path(adm0).read_text(encoding="utf-8"))["features"][0]
    ecrire("algerie.geojson", [{"type": "Feature", "properties": {"nom": "Algérie"},
                                "geometry": alleger(pays["geometry"], 0.02, 3)}],
           "geoBoundaries DZA ADM0 (OpenStreetMap, Wambacher)", "ODbL 1.0")

    wilayas = json.loads(Path(adm1).read_text(encoding="utf-8"))["features"]
    alger = next(f for f in wilayas if f["properties"]["shapeName"] in ("Algiers", "Alger"))
    ecrire("alger_wilaya.geojson", [{"type": "Feature", "properties": {"nom": "Wilaya d'Alger"},
                                     "geometry": alleger(alger["geometry"], 0.001)}],
           "geoBoundaries DZA ADM1 (OpenStreetMap, Wambacher)", "ODbL 1.0")

    contour = max((p[0] for p in _polygones(alger["geometry"])), key=len)
    communes = []
    for f in json.loads(Path(adm3).read_text(encoding="utf-8"))["features"]:
        x, y = centre(f["geometry"])
        if dans_polygone(x, y, contour):
            communes.append({"type": "Feature",
                             "properties": {"nom": NOMS_FRANCAIS.get(f["properties"]["shapeName"],
                                                                 f["properties"]["shapeName"]),
                                            "lon": round(x, 4), "lat": round(y, 4)},
                             "geometry": alleger(f["geometry"], 0.0008)})
    ecrire("alger_communes.geojson", communes,
           "geoBoundaries DZA ADM3 (OpenStreetMap)", "CC BY-SA 2.0")


if __name__ == "__main__":
    main(*sys.argv[1:4])
