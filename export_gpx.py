"""Rassemble les GPX des parcours VisuGPX de l'onglet Parcours.

Chaque trace VisuGPX publique se télécharge à l'adresse /dl/<code>.gpx.
Résultat : gpx/<date nom>/<nom>.gpx, publié sur la branche gpx-export
(workflow « Export GPX », lancé à la main).
"""
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
SORTIE = BASE / "gpx"


def lire(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; OGravel-parcours; +https://gabydelphine.github.io/Calendrier-des-sorties-OGRAVEL/)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def nom_fichier(texte):
    texte = unicodedata.normalize("NFC", texte)
    texte = re.sub(r'[\\/:*?"<>|#]+', "-", texte).strip(" .")
    return re.sub(r"\s+", " ", texte)[:90]


def main():
    parcours = json.loads((BASE / "app" / "parcours.json").read_text(encoding="utf-8"))["parcours"]
    ok, ko = 0, []
    for p in parcours:
        m = re.search(r"visugpx\.com/([A-Za-z0-9]{10})$", p.get("lien") or "")
        if not m:
            continue
        nom = p.get("nom") or "Sortie"
        dossier = SORTIE / nom_fichier(f"{p.get('date', '')} {nom}")
        try:
            donnees = lire(f"https://www.visugpx.com/dl/{m.group(1)}.gpx")
        except Exception as exc:
            ko.append(f"{nom} : {exc}")
            continue
        if b"<gpx" not in donnees[:500]:
            ko.append(f"{nom} : réponse qui n'est pas un GPX")
            continue
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / (nom_fichier(nom) + ".gpx")).write_bytes(donnees)
        print(f"+ {dossier.name} ({len(donnees) // 1024} Ko)")
        ok += 1
        time.sleep(2)
    print(f"{ok} GPX récupérés")
    for k in ko:
        print("!", k)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
