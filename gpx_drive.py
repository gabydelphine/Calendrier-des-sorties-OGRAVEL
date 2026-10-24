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
# Copie des GPX dans l'appli : le bouton « GPX » les envoie directement aux applis du téléphone.
COPIES = BASE / "app" / "gpx"
TELECHARGER = "https://drive.google.com/uc?export=download&id={}"
VOIR = "https://drive.google.com/file/d/{}/view"
# Dénivelé : variations ignorées en dessous du seuil. 4 m pour VisuGPX et Komoot (altitudes
# déjà propres, réglé sur les chiffres de VisuGPX). Pour un GPX brut (montre, compteur, export
# d'appli), altitudes lissées sur LISSAGE mètres de parcours (réglé sur les D+ annoncés : ±5 %).
SEUIL = 4
LISSAGE = 400


def dplus_annonce(fichier):
    """D+ écrit dans le nom du fichier (« ..._22km_276m », « challenge 3000m ») ou None."""
    n = joli_nom(fichier).lower()
    m = re.findall(r"(?<![\d.,k])(\d{2,4})\s?m(?:\s?d\+)?(?![a-z])", n)
    return int(m[-1]) if m and 30 <= int(m[-1]) <= 6000 else None


def joli_nom(fichier):
    """« 2026_10_24_challenge_3000m_116km-25430012-1791880543-978.gpx » -> « challenge 3000m 116km »."""
    n = re.sub(r"\.gpx$", "", fichier, flags=re.I)
    n = re.sub(r"(-\d{6,})+(-\d{1,5})?$", "", n)  # numéros ajoutés par les sites
    n = re.sub(r"^\d{4}[_-]\d{2}[_-]\d{2}[_ -]*", "", n)  # date en tête
    n = re.sub(r"[_]+", " ", n).strip()
    return n or fichier


def lire(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; OGravel-parcours)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def charger(chemin, defaut):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def mesurer(gpx, seuil=0, lissage=0):
    """Distance (km) et dénivelé positif (m) d'un fichier GPX.
    seuil : variation d'altitude ignorée (m) ; lissage : moyenne des altitudes sur ce nombre
    de mètres de parcours, pour un GPX brut dont l'altitude « tremble »."""
    texte = gpx.decode("utf-8", "replace")
    pts = re.findall(r'<(?:trkpt|rtept)[^>]*?lat="([-\d.]+)"[^>]*?lon="([-\d.]+)"[^>]*?>(.*?)</(?:trkpt|rtept)>', texte, re.S)
    if not pts:  # lon avant lat
        pts = [(la, lo, rest) for lo, la, rest in
               re.findall(r'<(?:trkpt|rtept)[^>]*?lon="([-\d.]+)"[^>]*?lat="([-\d.]+)"[^>]*?>(.*?)</(?:trkpt|rtept)>', texte, re.S)]
    dist, prec, D, E = 0.0, None, [], []
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
            D.append(dist * 1000)
            E.append(float(m.group(1)))
    if lissage and E:  # moyenne glissante sur ± lissage/2 mètres
        lisse, j0, j1, somme = [], 0, 0, 0.0
        for i in range(len(E)):
            while j1 < len(E) and D[j1] <= D[i] + lissage / 2:
                somme += E[j1]
                j1 += 1
            while D[j0] < D[i] - lissage / 2:
                somme -= E[j0]
                j0 += 1
            lisse.append(somme / (j1 - j0))
        E = lisse
    dplus, ref = 0.0, None
    for ele in E:
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
    gardes = set()
    for s in index.get("sorties", []):
        choix = []
        for f in s.get("gpx", []):
            cle = f"{f['id']}|{f.get('modifie', '')}|s{SEUIL}-l{LISSAGE}"
            copie = COPIES / f"{f['id']}.gpx"
            if cle not in cache or not copie.exists():
                try:
                    gpx = lire(TELECHARGER.format(f["id"]))
                except Exception as exc:
                    print(f"! {s['nom']} / {f['nom']} : {exc}", file=sys.stderr)
                    continue
                if b"<gpx" not in gpx[:2000]:
                    print(f"! {s['nom']} / {f['nom']} : pas lisible (fichier partagé par lien ?)", file=sys.stderr)
                    continue
                COPIES.mkdir(exist_ok=True)
                copie.write_bytes(gpx)
                gardes.add(copie.name)
                if cle in cache:
                    choix.append((f, cache[cle]))
                    continue
                o = origine(gpx)
                if o in ("visugpx", "komoot"):
                    km, dplus = mesurer(gpx, SEUIL)
                else:
                    km, dplus = mesurer(gpx, 0, LISSAGE)
                    dplus = dplus_annonce(f["nom"]) or dplus  # le chiffre de l'auteur prime
                cache[cle] = {"km": km, "dplus": dplus, "origine": o}
            gardes.add(copie.name)
            choix.append((f, cache[cle]))
        if not choix:
            # Dossier encore vide : la sortie s'affiche avec « Trace bientôt disponible ».
            parcours.append({"date": s["date"], "nom": s["nom"], "en_attente": True})
            continue
        # VisuGPX d'abord, puis tout autre GPX, Komoot en dernier ; puis le plus récent.
        rang = {"visugpx": 0, "autre": 1, "komoot": 2}
        choix.sort(key=lambda c: (rang.get(c[1]["origine"], 1), c[0].get("nom", "")))
        f, m = choix[0]
        entree = {"date": s["date"], "nom": s["nom"], "distance_km": m["km"], "denivele_m": m["dplus"],
                  "lien": VOIR.format(f["id"]), "telecharger": TELECHARGER.format(f["id"]),
                  "fichier": f"gpx/{f['id']}.gpx", "nom_fichier": joli_nom(f["nom"])}
        if len(choix) > 1:  # plusieurs parcours (ex. 2000 m et 3000 m) ou plusieurs étapes
            entree["fichiers"] = [{"nom": joli_nom(ff["nom"]), "distance_km": mm["km"], "denivele_m": mm["dplus"],
                                   "lien": VOIR.format(ff["id"]), "telecharger": TELECHARGER.format(ff["id"]),
                                   "fichier": f"gpx/{ff['id']}.gpx"}
                                  for ff, mm in choix]
        parcours.append(entree)
        print(f"+ {s['date']} {s['nom']} : {m['km']} km, {m['dplus']} m ({m['origine']})")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if not any(not p.get("en_attente") for p in parcours) and index.get("sorties"):
        print("Aucun GPX lisible : parcours inchangés")
        return
    parcours.sort(key=lambda p: p["date"], reverse=True)
    for vieux in COPIES.glob("*.gpx"):  # GPX retirés du Drive
        if vieux.name not in gardes:
            vieux.unlink()
    PARCOURS.write_text(json.dumps({"_aide": "Rempli par gpx_drive.py depuis le dossier gpx du Google Drive ÔGravel.",
                                    "parcours": parcours}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(parcours)} parcours, dont {sum(1 for p in parcours if p.get('en_attente'))} en attente de GPX")


if __name__ == "__main__":
    main()
