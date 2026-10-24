"""Ajoute dans l'onglet Parcours les traces Komoot de Thierry des sorties ÔGravel.

Chaque jour :
1. on mémorise les dates des sorties du calendrier (events.json et
   helloasso.json) dans sorties-historique.json, car events.json ne garde
   que les sorties à venir ;
2. on lit le profil Komoot public de Thierry (15 dernières sorties, sans
   être connecté, pages autorisées par le robots.txt de Komoot) ;
3. une trace enregistrée le jour d'une sortie du calendrier (ou pendant une
   sortie de plusieurs jours) est ajoutée à app/parcours.json.

Pour retirer une trace ajoutée par erreur : supprimer son bloc dans
app/parcours.json et mettre son numéro dans la liste "_exclus".
"""
import datetime
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
UTILISATEUR = "1261516550100"  # Thierry SCHIAVI - Ô Gravel !
PROFIL = f"https://www.komoot.com/fr-fr/user/{UTILISATEUR}"
TOUR = "https://www.komoot.com/fr-fr/tour/{}"
VISUGPX = "https://www.visugpx.com/membres/1289/"  # traces de Thierry Ô Gravel ! (pages autorisées par le robots.txt)
PARCOURS = BASE / "app" / "parcours.json"
HISTORIQUE = BASE / "sorties-historique.json"
VUS = BASE / "komoot-vus.json"
FENETRE_JOURS = 60  # on ne rattache que les sorties des 60 derniers jours

MOIS = {"janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12}


def lire(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; OGravel-parcours; +https://gabydelphine.github.io/Calendrier-des-sorties-OGRAVEL/)",
        "Accept-Language": "fr-FR,fr;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def charger(chemin, defaut):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def ecrire(chemin, donnees):
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def memoriser_sorties():
    """Ajoute à l'historique les sorties actuellement au calendrier."""
    historique = charger(HISTORIQUE, {"_aide": "Dates des sorties ÔGravel déjà vues au calendrier (sert à rattacher les traces Komoot).", "sorties": []})
    connues = {(s["date"], s.get("title", "")) for s in historique["sorties"]}
    nouvelles = []
    for e in charger(BASE / "events.json", {}).get("events", []):
        nouvelles.append({"date": e["date"], "end_date": e.get("end_date"), "title": e.get("title", "")})
    for h in charger(BASE / "helloasso.json", {}).get("evenements", []):
        if h.get("date"):
            nouvelles.append({"date": h["date"], "end_date": h.get("end_date"), "title": h.get("titre", "")})
    for s in nouvelles:
        if (s["date"], s["title"]) not in connues:
            historique["sorties"].append(s)
            connues.add((s["date"], s["title"]))
    historique["sorties"].sort(key=lambda s: s["date"])
    ecrire(HISTORIQUE, historique)
    return historique["sorties"]


def infos_tour(html):
    """Nom, date, distance (km) et D+ (m) d'une page de sortie Komoot."""
    nom = None
    m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html) or re.search(r"<title>([^<]+)</title>", html)
    if m:
        nom = re.sub(r"\s*\|.*$", "", m.group(1)).strip()
        nom = nom.replace("&#x27;", "'").replace("&#39;", "'").replace("&quot;", '"').replace("&amp;", "&")
    date = None
    m = re.search(r'"date"\s*:\s*"(\d{4}-\d{2}-\d{2})T', html)
    if m:
        date = m.group(1)
    else:
        m = re.search(r"(\d{1,2})\s+(" + "|".join(MOIS) + r")\s+(\d{4})", html)
        if m:
            date = datetime.date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1))).isoformat()
    km = dplus = None
    m = re.search(r'\\?"distance\\?"\s*:\s*([\d.]+)', html)
    if m:
        km = round(float(m.group(1)) / 1000)
    m = re.search(r'\\?"elevation_?[uU]p\\?"\s*:\s*([\d.]+)', html)
    if m:
        dplus = round(float(m.group(1)))
    if km is None:
        # Repli : texte affiché, par ex. « 53,2 km » dans la description de la page.
        m = re.search(r'<meta[^>]+(?:name|property)="(?:og:)?description"[^>]+content="([^"]+)"', html)
        texte = m.group(1) if m else ""
        mk = re.search(r"(\d+(?:[.,]\d+)?)\s*km", texte)
        if mk:
            km = round(float(mk.group(1).replace(",", ".")))
        md = re.search(r"(\d[\d\s .]*)\s*m\b[^.]{0,40}?(?:dénivelé|montée|D\+)|(?:dénivelé|montée|D\+)[^\d]{0,30}(\d[\d\s .]*)\s*m", texte, re.I)
        if md:
            dplus = int(re.sub(r"\D", "", md.group(1) or md.group(2)))
    if km is None:
        # Aide au réglage : montre où apparaissent km et dénivelé dans la page.
        for mot in ("distance", "elevation", " km"):
            i = html.find(mot)
            if i >= 0:
                print("   [indice]", repr(html[max(0, i - 60):i + 80]))
    return nom, date, km, dplus


def sortie_du_jour(date, sorties, aujourdhui):
    jour = datetime.date.fromisoformat(date)
    if jour > aujourdhui or jour < aujourdhui - datetime.timedelta(days=FENETRE_JOURS):
        return None
    for s in sorties:
        debut = datetime.date.fromisoformat(s["date"])
        fin = datetime.date.fromisoformat(s["end_date"]) if s.get("end_date") else debut
        if debut <= jour <= fin:
            return s
    return None


def main():
    aujourdhui = datetime.date.today()
    sorties = memoriser_sorties()
    parcours = charger(PARCOURS, {"parcours": []})
    exclus = {str(x) for x in parcours.get("_exclus", [])}
    deja = {m.group(1) for p in parcours["parcours"] for cle in ("lien", "lien_komoot")
            if (m := re.search(r"/tour/(\d+)", p.get(cle) or ""))}
    vus = charger(VUS, {})

    html = lire(PROFIL)
    ids = []
    for i in re.findall(r"/tour/(\d+)", html):
        if i not in ids:
            ids.append(i)
    print(f"{len(ids)} sorties sur le profil Komoot")
    if not ids:
        print(html[:2000])
        raise RuntimeError("Aucune sortie trouvée sur le profil Komoot")

    ajouts = 0
    for i in ids:
        if i in deja or i in exclus:
            continue
        if i not in vus or vus[i].get("km") is None:
            time.sleep(1)
            try:
                nom, date, km, dplus = infos_tour(lire(TOUR.format(i)))
            except Exception as exc:  # une page en erreur ne bloque pas les autres
                print(f"! {i} : {exc}", file=sys.stderr)
                continue
            vus[i] = {"nom": nom, "date": date, "km": km, "dplus": dplus}
            print(f"{i} : {date} {nom} {km} km {dplus} m")
        t = vus[i]
        if not t.get("date"):
            continue
        s = sortie_du_jour(t["date"], sorties, aujourdhui)
        if not s:
            continue
        bloc = {"date": t["date"], "nom": t.get("nom") or s["title"] or "Sortie ÔGravel",
                "lien": TOUR.format(i), "auto": True}
        if t.get("km"):
            bloc["distance_km"] = t["km"]
        if t.get("dplus"):
            bloc["denivele_m"] = t["dplus"]
        parcours["parcours"].append(bloc)
        deja.add(i)
        ajouts += 1
        print(f"+ ajouté : {bloc['date']} {bloc['nom']} (sortie « {s['title']} »)")

    ecrire(VUS, vus)
    try:
        ajouts += visugpx(parcours, sorties, aujourdhui)
    except Exception as exc:  # VisuGPX indisponible : on garde les liens Komoot
        print(f"! VisuGPX : {exc}", file=sys.stderr)
    if ajouts:
        parcours["parcours"].sort(key=lambda p: p.get("date", ""), reverse=True)
        ecrire(PARCOURS, parcours)
    print(f"{ajouts} parcours ajoutés")


def traces_visugpx():
    """Traces publiques de Thierry sur VisuGPX : code, nom, date, km, D+."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(lire(VISUGPX), "html.parser")
    traces, vus = [], set()
    for a in soup.find_all("a", href=re.compile(r"^/[A-Za-z0-9]{10}$")):
        code = a["href"][1:]
        if code in vus:
            continue
        bloc, texte = a, ""
        for _ in range(6):  # remonte jusqu'au bloc de CETTE trace (date, km, D+)
            parent = bloc.parent
            if parent is None:
                break
            # S'arrêter avant un bloc qui contient aussi d'autres traces.
            autres = {x["href"] for x in parent.find_all("a", href=re.compile(r"^/[A-Za-z0-9]{10}$"))}
            if len(autres) > 1:
                break
            bloc = parent
            texte = bloc.get_text(" ", strip=True)
            if re.search(r"\d{2}\.\d{2}\.\d{4}", texte) and re.search(r"km", texte):
                break
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", texte)
        if not m:
            continue
        vus.add(code)
        km = re.search(r"([\d.,]+)\s*km", texte)
        dp = re.search(r"D\+\s*([\d\s]+?)\s*m\b", texte)
        traces.append({"code": code, "nom": a.get_text(" ", strip=True),
                       "date": f"{m.group(3)}-{m.group(2)}-{m.group(1)}",
                       "km": round(float(km.group(1).replace(",", "."))) if km else None,
                       "dplus": int(re.sub(r"\D", "", dp.group(1))) if dp else None})
    return traces


def ressemble(nom, sortie):
    """La trace VisuGPX est-elle celle de la sortie ? (la date VisuGPX est la date
    d'ajout de la trace : Thierry en ajoute parfois plusieurs le même jour)."""
    import difflib
    def simple(t):
        import unicodedata
        t = unicodedata.normalize("NFKD", t or "")
        return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if not unicodedata.combining(c)).lower()).strip()
    n, s = simple(nom), simple(sortie)
    if re.search(r"\bo ?gravel\b|\bogravel\b", n):
        return True
    return difflib.SequenceMatcher(None, n, s).ratio() >= 0.6


def visugpx(parcours, sorties, aujourdhui):
    """Préfère la trace VisuGPX (parcours proposé, GPX en accès libre) publiée
    le jour d'une sortie : remplace le lien Komoot, ou ajoute la sortie."""
    traces = traces_visugpx()
    print(f"{len(traces)} traces sur VisuGPX")
    exclus = {str(x) for x in parcours.get("_exclus", [])}
    changements = 0
    for t in traces:
        if t["code"] in exclus or any(t["code"] in (p.get("lien") or "") for p in parcours["parcours"]):
            continue
        if any(p.get("date") == t["date"] and "visugpx.com" in (p.get("lien") or "") for p in parcours["parcours"]):
            continue  # une seule trace VisuGPX par sortie
        existant = next((p for p in parcours["parcours"]
                         if p.get("date") == t["date"] and "visugpx.com" not in (p.get("lien") or "")), None)
        s = sortie_du_jour(t["date"], sorties, aujourdhui)
        titre_sortie = (existant or {}).get("nom") or (s or {}).get("title", "")
        if not (existant or s) or not ressemble(t["nom"], titre_sortie):
            continue
        if existant:
            existant["lien_komoot"] = existant.get("lien_komoot") or existant.get("lien")
        else:
            existant = {"date": t["date"], "nom": t["nom"], "auto": True}
            parcours["parcours"].append(existant)
        existant["lien"] = "https://www.visugpx.com/" + t["code"]
        if t["km"]:
            existant["distance_km"] = t["km"]
        if t["dplus"]:
            existant["denivele_m"] = t["dplus"]
        changements += 1
        print(f"+ VisuGPX : {t['date']} {t['nom']}")
    return changements


if __name__ == "__main__":
    main()
