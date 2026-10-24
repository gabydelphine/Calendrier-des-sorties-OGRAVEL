"""Onglet Parcours : les GPX rangés dans le dossier « gpx » du Google Drive ÔGravel.

Chaque sortie du calendrier a son dossier « AAAA-MM-JJ Nom » sur le Drive
(créé automatiquement par le script Google « majDossiers »). On y dépose le GPX
à la main ; à chaque passage, le robot :
1. mémorise les sorties du calendrier (sorties-historique.json, lu par le script Google) ;
2. lit la liste des dossiers et des GPX (application Web du script Google, adresse
   dans app/config.json, clé gpx_drive) ;
3. pour chaque sortie qui a un GPX : télécharge le fichier, calcule distance et D+,
   et l'inscrit dans app/parcours.json. S'il y a plusieurs GPX, celui de VisuGPX
   est préféré à celui de Komoot.
"""
import json
import math
import re
import sys
import urllib.request
from pathlib import Path

from komoot import memoriser_sorties

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "app" / "config.json"
PARCOURS = BASE / "app" / "parcours.json"
CACHE = BASE / "gpx-cache.json"
TELECHARGER = "https://drive.google.com/uc?export=download&id={}"
VOIR = "https://drive.google.com/file/d/{}/view"


def lire(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; OGravel-parcours)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def charger(chemin, defaut):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def mesurer(gpx, seuil=0):
    """Distance (km) et dénivelé positif (m) d'un fichier GPX.
    seuil : variation d'altitude ignorée (m), utile pour un GPX brut de montre ou de téléphone."""
    texte = gpx.decode("utf-8", "replace")
    pts = re.findall(r'<(?:trkpt|rtept)[^>]*?lat="([-\d.]+)"[^>]*?lon="([-\d.]+)"[^>]*?>(.*?)</(?:trkpt|rtept)>', texte, re.S)
    if not pts:  # lon avant lat
        pts = [(la, lo, rest) for lo, la, rest in
               re.findall(r'<(?:trkpt|rtept)[^>]*?lon="([-\d.]+)"[^>]*?lat="([-\d.]+)"[^>]*?>(.*?)</(?:trkpt|rtept)>', texte, re.S)]
    dist, dplus, prec, ref = 0.0, 0.0, None, None
    for la, lo, rest in pts:
        la, lo = float(la), float(lo)
        if prec:
            p1, p2 = math.radians(prec[0]), math.radians(la)
            dp, dl = p2 - p1, math.radians(lo - prec[1])
            a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
            dist += 2 * 6371.0 * math.asin(math.sqrt(a))
        prec = (la, lo)
        m = re.search(r"<ele>([-\d.]+)</ele>", rest)
        if m:
            ele = float(m.group(1))
            if ref is None:
                ref = ele
            elif ele - ref >= seuil:
                dplus += ele - ref
                ref = ele
            elif ele < ref:
                ref = ele
    return round(dist), round(dplus)


def origine(gpx):
    debut = gpx[:600].decode("utf-8", "replace").lower()
    return "komoot" if "komoot" in debut else "visugpx" if "visugpx" in debut else "autre"


def main():
    memoriser_sorties()
    adresse = charger(CONFIG, {}).get("gpx_drive")
    if not adresse:
        print("Pas d'adresse gpx_drive dans app/config.json : parcours inchangés")
        return
    index = json.loads(lire(adresse))
    cache = charger(CACHE, {})
    parcours = []
    for s in index.get("sorties", []):
        choix = []
        for f in s.get("gpx", []):
            cle = f"{f['id']}|{f.get('modifie', '')}"
            if cle not in cache:
                try:
                    gpx = lire(TELECHARGER.format(f["id"]))
                except Exception as exc:
                    print(f"! {s['nom']} / {f['nom']} : {exc}", file=sys.stderr)
                    continue
                if b"<gpx" not in gpx[:2000]:
                    print(f"! {s['nom']} / {f['nom']} : pas lisible (fichier partagé par lien ?)", file=sys.stderr)
                    continue
                o = origine(gpx)  # VisuGPX et Komoot lissent déjà les altitudes
                km, dplus = mesurer(gpx, 0 if o in ("visugpx", "komoot") else 3)
                cache[cle] = {"km": km, "dplus": dplus, "origine": o}
            choix.append((f, cache[cle]))
        if not choix:
            continue
        # VisuGPX d'abord, puis tout autre GPX, Komoot en dernier ; puis le plus récent.
        rang = {"visugpx": 0, "autre": 1, "komoot": 2}
        f, m = sorted(choix, key=lambda c: (rang.get(c[1]["origine"], 1), c[0].get("modifie", "")), reverse=False)[0]
        parcours.append({"date": s["date"], "nom": s["nom"], "distance_km": m["km"], "denivele_m": m["dplus"],
                         "lien": VOIR.format(f["id"]), "telecharger": TELECHARGER.format(f["id"])})
        print(f"+ {s['date']} {s['nom']} : {m['km']} km, {m['dplus']} m ({m['origine']})")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if not parcours and index.get("sorties"):
        print("Aucun GPX lisible : parcours inchangés")
        return
    parcours.sort(key=lambda p: p["date"], reverse=True)
    PARCOURS.write_text(json.dumps({"_aide": "Rempli par gpx_drive.py depuis le dossier gpx du Google Drive ÔGravel.",
                                    "parcours": parcours}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(parcours)} parcours")


if __name__ == "__main__":
    main()
