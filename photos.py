"""Récupère les photos de l'album Google Photos partagé d'ÔGravel.

Lit la page publique de l'album (le lien de partage indiqué dans
app/config.json, clé photos_url) et écrit app/photos.json avec les adresses
des photos, pour le carrousel de l'onglet Photos de l'appli.
En cas d'échec, le fichier précédent est conservé.
"""
import csv
import datetime
import difflib
import io
import json
import unicodedata
import re
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "app" / "config.json"
SORTIE = BASE / "app" / "photos.json"
MAXI = 3000  # nombre de photos gardées (galerie et carrousel)
PARIS = datetime.timezone(datetime.timedelta(hours=2))


def sorties_connues():
    """Toutes les sorties ÔGravel connues : calendrier, historique, HelloAsso et parcours."""
    def lire_json(chemin):
        try:
            return json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    liste = []
    for e in lire_json(BASE / "events.json").get("events", []):
        liste.append((e["date"], e.get("end_date"), e.get("title", "")))
    for e in lire_json(BASE / "sorties-historique.json").get("sorties", []):
        liste.append((e["date"], e.get("end_date"), e.get("title", "")))
    for e in lire_json(BASE / "helloasso.json").get("evenements", []):
        if e.get("date"):
            liste.append((e["date"], e.get("end_date"), e.get("titre", "")))
    for e in lire_json(CONFIG.parent / "parcours.json").get("parcours", []):
        if e.get("date"):
            liste.append((e["date"], None, e.get("nom", "")))
    return liste


def photos_manuelles():
    """Sortie (et date) données à la main pour une photo précise (photos-titres.json, clé « photos »)."""
    try:
        return json.loads((BASE / "photos-titres.json").read_text(encoding="utf-8")).get("photos", {})
    except (OSError, ValueError):
        return {}


def titres_manuels():
    """Titres donnés à la main pour les jours sans sortie au calendrier (photos-titres.json)."""
    try:
        return json.loads((BASE / "photos-titres.json").read_text(encoding="utf-8")).get("titres", {})
    except (OSError, ValueError):
        return {}


FORMULAIRE_CSV = ("https://docs.google.com/spreadsheets/d/e/2PACX-1vRtNWXORoF7_h4uk8R1-d4LE8cQLpZdGZlNGUBh01Kl7IJmO-MbWcCQgakz02H0_fXiAg_aYR6UGg9A"
                  "/pub?gid=1122563515&single=true&output=csv")
AGENDA = "https://gabydelphine.github.io/Agenda-Gravel-autres-associations/events.json"


def simplifier(texte):
    """Minuscules, sans accents ni ponctuation : « Dralhà-Blanca » -> « dralha blanca »."""
    texte = unicodedata.normalize("NFD", str(texte or ""))
    texte = "".join(c for c in texte if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9#]+", " ", texte).strip()


def date_iso(valeur):
    """Accepte 2026-10-04, 04/10/2026 ou 4/10/26."""
    valeur = (valeur or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", valeur):
        return valeur
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", valeur)
    if m:
        j, mo, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        a = a + 2000 if a < 100 else a
        try:
            return datetime.date(a, mo, j).isoformat()
        except ValueError:
            return None
    return None


def titres_formulaire(sorties):
    """Noms d'événements donnés par les membres dans l'appli (formulaire Google),
    corrigés d'après les événements connus (fautes, accents, majuscules)."""
    try:
        _, texte = lire(FORMULAIRE_CSV)
    except Exception as exc:
        print(f"! Formulaire : {exc}")
        return {}
    connus = [(d, f, t) for d, f, t in sorties if t]
    try:
        _, agenda = lire(AGENDA)
        connus += [(e["date"], e.get("end_date"), e.get("title", "")) for e in json.loads(agenda).get("events", []) if e.get("title")]
    except Exception as exc:
        print(f"! Agenda : {exc}")
    reponses = {}
    for ligne in list(csv.reader(io.StringIO(texte)))[1:]:
        if len(ligne) < 3 or not ligne[1].strip():
            continue
        date = date_iso(ligne[2])
        if not date:
            continue
        reponses.setdefault(date, []).append(ligne[1].strip())
    titres = {}
    for date, noms in reponses.items():
        jour = datetime.date.fromisoformat(date)
        def proximite(d):  # les événements proches de la date passent en premier
            try:
                return abs((datetime.date.fromisoformat(d) - jour).days)
            except ValueError:
                return 999
        # Meilleure ressemblance ; à ressemblance égale, l'événement le plus proche de la date.
        candidats = {}
        for d, f, titre in connus:
            ecart = 0 if (f and d <= date <= f) else proximite(d)
            candidats[titre] = min(ecart, candidats.get(titre, 999))
        choisi = None
        for nom in noms:
            s = simplifier(nom)
            notes = [(difflib.SequenceMatcher(None, s, simplifier(c)).ratio(), -e, c) for c, e in candidats.items()]
            if notes:
                note, _, meilleur = max(notes)
                if note >= 0.72:
                    choisi = meilleur
                    break
        if not choisi:
            # Nom inconnu : le plus fréquent des noms donnés, présenté proprement.
            nom = max(noms, key=lambda n: sum(simplifier(m) == simplifier(n) for m in noms))
            choisi = re.sub(r"\s+", " ", nom).strip()
            choisi = choisi[0].upper() + choisi[1:] if choisi else choisi
            print(f"   nom libre pour le {date} : {choisi}")
        titres[date] = choisi
    print(f"{len(titres)} jour(s) titré(s) par les membres")
    return titres


def sortie_du_jour(date, sorties, manuels=None):
    if manuels and manuels.get(date):
        return manuels[date]
    for debut, fin, titre in sorties:
        if debut <= date <= (fin or debut):
            return titre
    return None


def lire(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
        "Accept-Language": "fr-FR,fr;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.geturl(), r.read().decode("utf-8", "replace")


def main():
    album = json.loads(CONFIG.read_text(encoding="utf-8")).get("photos_url")
    if not album:
        raise RuntimeError("Pas d'album dans app/config.json (photos_url)")
    adresse, html = lire(album)
    print(f"Album lu : {len(html)} caractères")

    # Dans la page, chaque photo apparaît comme ["https://lh3.googleusercontent.com/pw/…", largeur, hauteur, …].
    photos, vues = [], set()
    for m in re.finditer(r'\["(https://lh3\.googleusercontent\.com/pw/[A-Za-z0-9_\-]+)",(\d+),(\d+)', html):
        url, largeur, hauteur = m.group(1), int(m.group(2)), int(m.group(3))
        if url in vues or largeur < 300 or hauteur < 300:
            continue  # doublons, avatars et vignettes
        vues.add(url)
        photo = {"url": url, "largeur": largeur, "hauteur": hauteur}
        # Juste après l'adresse, la page donne la date de prise de vue (millisecondes).
        suite = html[m.end():m.end() + 600]
        if len(photos) == 0:
            print("   [indice]", repr(suite[:300]))
        t = re.search(r"\b(1[4-9]\d{11})\b", suite)
        if t:
            moment = datetime.datetime.fromtimestamp(int(t.group(1)) / 1000, PARIS)
            photo["date"] = moment.date().isoformat()
        photos.append(photo)
    if not photos:
        # Repli : toute adresse de photo de l'album, sans dimensions.
        for url in re.findall(r"https://lh3\.googleusercontent\.com/pw/[A-Za-z0-9_\-]{40,}", html):
            if url not in vues:
                vues.add(url)
                photos.append({"url": url})
    print(f"{len(photos)} photos trouvées")
    if not photos:
        print(html[:1500])
        raise RuntimeError("Aucune photo trouvée : fichier précédent conservé")

    # La page de l'album ne montre que les ~300 photos les plus récentes :
    # on garde aussi celles déjà connues (fichier précédent) pour ne rien perdre.
    try:
        anciennes = json.loads(SORTIE.read_text(encoding="utf-8")).get("photos", [])
    except (OSError, ValueError):
        anciennes = []
    gardees = 0
    for p in anciennes:
        if p.get("url") and p["url"] not in vues:
            vues.add(p["url"])
            p.pop("sortie", None)  # retitrée ci-dessous avec les règles du jour
            photos.append(p)
            gardees += 1
    print(f"{gardees} photos plus anciennes gardées du fichier précédent")

    # Tri par date (les plus récentes d'abord) et association à la sortie du jour.
    sorties = sorties_connues()
    # Priorité : titres donnés à la main > noms donnés par les membres > calendrier.
    manuels = {**titres_formulaire(sorties), **titres_manuels()}
    une_par_une = photos_manuelles()
    for p in photos:
        fixe = une_par_une.get(p["url"])
        if fixe:  # photo rangée à la main (par ex. sans date de prise de vue)
            p["sortie"] = fixe.get("sortie") or p.get("sortie")
            if fixe.get("date"):
                p["date"] = fixe["date"]
            continue
        if p.get("date"):
            titre = sortie_du_jour(p["date"], sorties, manuels)
            if titre:
                p["sortie"] = titre
    photos.sort(key=lambda p: p.get("date", ""), reverse=True)
    print(f"{sum(1 for p in photos if p.get('date'))} photos datées, {sum(1 for p in photos if p.get('sortie'))} rattachées à une sortie")
    inconnues = sorted({p["date"] for p in photos if p.get("date") and not p.get("sortie")}, reverse=True)
    print("Jours sans sortie connue :", ", ".join(inconnues) or "aucun")
    SORTIE.write_text(json.dumps({
        "updated": datetime.date.today().isoformat(),
        "album": album,
        "photos": photos[:MAXI],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
