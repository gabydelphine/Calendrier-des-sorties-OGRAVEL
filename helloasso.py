"""Lit la page HelloAsso d'ÔGravel et écrit helloasso.json.

Pour chaque événement en ligne : titre, adresse, dates, date limite
d'inscription, prix du moment, places restantes et état
(« ouvert » ou « cloture » quand c'est complet ou que la date limite
est passée). L'appli s'en sert pour afficher le bouton d'inscription.
En cas d'échec, le fichier précédent est conservé.
"""
import datetime
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

ORGA = "o-gravel"
BASE = "https://www.helloasso.com"
PAGE_ORGA = f"{BASE}/associations/{ORGA}"
SORTIE = Path(__file__).with_name("helloasso.json")
PARIS = datetime.timezone(datetime.timedelta(hours=1))  # assez précis pour une date limite à 23h59

MOIS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
M = "|".join(MOIS)
JOUR_SEMAINE = r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+"

COMPLET = [
    "toutes les places disponibles en ligne ont été vendues",
    "cet événement est complet",
    "l'événement est complet",
    "plus de places disponibles",
]
TERMINE = [
    "les inscriptions sont closes",
    "les inscriptions sont fermées",
    "les inscriptions sont terminées",
    "la billetterie est fermée",
    "la billetterie est terminée",
    "cette billetterie est terminée",
    "vente terminée",
    "n'est plus disponible",
]


def lire(url):
    # HelloAsso filtre les robots : on se présente comme un navigateur
    # (curl_cffi imite Chrome), avec repli sur urllib.
    try:
        from curl_cffi import requests as cr
        r = cr.get(url, impersonate="chrome", timeout=30, headers={"Accept-Language": "fr-FR,fr;q=0.9"})
        print(f"{r.status_code} {url}")
        r.raise_for_status()
        return r.text
    except ImportError:
        pass
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def liens_evenements(html):
    motif = re.compile(rf"/associations/{ORGA}/evenements/([a-z0-9-]+)")
    vus = []
    for slug in motif.findall(html):
        if slug not in vus:
            vus.append(slug)
    return [f"{PAGE_ORGA}/evenements/{s}" for s in vus]


def date_fr(jour, mois, annee):
    try:
        return datetime.date(int(annee), MOIS[mois.lower()], int(jour))
    except (ValueError, KeyError):
        return None


def dates_evenement(texte, aujourdhui):
    """« Le 17 octobre 2026 », « Du 03 au 08 avril 2027 », « Du 30 avril au 2 mai 2027 »."""
    m = re.search(rf"\bdu\s+(\d{{1,2}})(?:er)?\s+({M})?\s*(\d{{4}})?\s*au\s+(\d{{1,2}})(?:er)?\s+({M})\s+(\d{{4}})", texte, re.I)
    if m:
        fin = date_fr(m.group(4), m.group(5), m.group(6))
        debut = date_fr(m.group(1), m.group(2) or m.group(5), m.group(3) or m.group(6))
        if debut and fin and debut > fin:
            debut = debut.replace(year=debut.year - 1)
        return debut, fin
    m = re.search(rf"\b(?:le\s+)?(?:{JOUR_SEMAINE})?(\d{{1,2}})(?:er)?\s+({M})\s+(\d{{4}})", texte, re.I)
    if m:
        d = date_fr(*m.groups())
        return d, d
    return None, None


def date_limite(texte, reference):
    m = re.search(
        rf"clôture des inscriptions le\s+(?:{JOUR_SEMAINE})?(\d{{1,2}})(?:er)?\s+({M})(?:\s+(\d{{4}}))?"
        rf"(?:\s+à\s+(\d{{1,2}})\s*h\s*(\d{{2}})?)?", texte, re.I)
    if not m:
        return None
    jour, mois, annee, h, mn = m.groups()
    if not annee:
        # Sans année : la plus proche avant (ou le jour de) l'événement.
        ref = reference or datetime.date.today()
        annee = ref.year
        d = date_fr(jour, mois, annee)
        if d and d > ref:
            annee -= 1
    d = date_fr(jour, mois, annee)
    if not d:
        return None
    return datetime.datetime(d.year, d.month, d.day, int(h or 23), int(mn or 59), tzinfo=PARIS)


def tarifs(lignes, aujourdhui):
    """Tarifs : une ligne avec un prix suivie (de près) de « N places restantes »
    ou « Complet ». Les tarifs « jusqu'au <date> » échus et « du <date> » pas
    encore commencés sont écartés."""
    resultat = []
    for i, ligne in enumerate(lignes):
        mp = re.fullmatch(r"(\d+(?:[.,]\d{1,2})?)\s*€", ligne)
        if not mp:
            continue
        prix = float(mp.group(1).replace(",", "."))
        places = None
        complet = False
        for suivante in lignes[i + 1:i + 6]:
            if re.fullmatch(r"\d+(?:[.,]\d{1,2})?\s*€", suivante):
                break
            mr = re.search(r"(\d+)\s+places?\s+restantes?", suivante, re.I)
            if mr:
                places = int(mr.group(1))
                break
            if re.fullmatch(r"complet", suivante, re.I):
                complet = True
                break
        titre = next((l for l in reversed(lignes[max(0, i - 4):i]) if len(l) > 3 and "€" not in l), "")
        actif = True
        mj = re.search(rf"jusqu'au\s+(\d{{1,2}})(?:er)?\s+({M})\s+(\d{{4}})", titre, re.I)
        if mj and (d := date_fr(*mj.groups())) and d < aujourdhui:
            actif = False
        md = re.search(rf"\bdu\s+(\d{{1,2}})(?:er)?\s+({M})\s+(\d{{4}})", titre, re.I)
        if md and (d := date_fr(*md.groups())) and d > aujourdhui:
            actif = False
        if places is None and not complet:
            continue  # prix sans quota : option, repas, don…
        resultat.append({"titre": titre, "prix": prix, "places": 0 if complet else places, "actif": actif})
    return resultat


def montant(prix):
    return (f"{prix:.2f}".replace(".", ",") if prix % 1 else str(int(prix))) + " €"


def analyser(url, html, aujourdhui):
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", property="og:title")
    titre = (meta.get("content") if meta else "") or (soup.title.string if soup.title else "")
    titre = re.sub(r"\s*[-|–]\s*HelloAsso.*$", "", titre or "").strip()
    lignes = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]
    texte = " ".join(lignes)
    bas = texte.lower()

    # La date de l'événement est sur une ligne qui commence par « Le » ou « Du » ;
    # sinon on cherche dans tout le texte.
    debut = fin = None
    for ligne in lignes:
        if re.match(r"(le|du)\s+(\w+\s+)?\d", ligne, re.I):
            debut, fin = dates_evenement(ligne, aujourdhui)
            if debut:
                break
    if not debut:
        debut, fin = dates_evenement(texte, aujourdhui)
    robots = soup.find("meta", attrs={"name": "robots"})
    if not fin and robots and (m := re.search(r"unavailable_after:\s*(\d{4}-\d{2}-\d{2})", robots.get("content", ""))):
        fin = datetime.date.fromisoformat(m.group(1))
        debut = debut or fin
    limite = date_limite(texte, debut)
    liste = tarifs(lignes, aujourdhui)
    actifs = [t for t in liste if t["actif"]] or liste

    raison = None
    if any(p in bas for p in COMPLET) or (actifs and all(t["places"] == 0 for t in actifs)):
        raison = "complet"
    elif limite and datetime.datetime.now(PARIS) > limite:
        raison = "date limite passée"
    elif any(p in bas for p in TERMINE):
        raison = "inscriptions terminées"
    elif fin and fin < aujourdhui:
        raison = "événement passé"

    prix = sorted({t["prix"] for t in actifs if t["places"] != 0}) or sorted({t["prix"] for t in actifs})
    if not prix:
        prix = sorted({float(p.replace(",", ".")) for p in re.findall(r"(\d+(?:,\d{1,2})?)\s*€", texte)})[:1]
    if not prix:
        texte_prix = ""
    elif len(prix) == 1:
        texte_prix = montant(prix[0])
    else:
        texte_prix = f"{montant(prix[0])} – {montant(prix[-1])}"
    places = sum(t["places"] for t in actifs if t["places"] is not None) if actifs else None

    return {
        "titre": titre,
        "url": url,
        "date": debut.isoformat() if debut else None,
        "end_date": fin.isoformat() if fin and fin != debut else None,
        "date_limite": limite.isoformat() if limite else None,
        "prix": texte_prix,
        "places_restantes": places,
        "etat": "cloture" if raison else "ouvert",
        "raison": raison,
    }


def main():
    aujourdhui = datetime.date.today()
    html = lire(PAGE_ORGA)
    urls = liens_evenements(html)
    if not urls:
        print(html[:3000])
        raise RuntimeError("Aucun événement trouvé sur la page HelloAsso : fichier précédent conservé")
    evenements = []
    for url in urls:
        time.sleep(1)
        try:
            e = analyser(url, lire(url), aujourdhui)
        except Exception as exc:  # une page en erreur ne bloque pas les autres
            print(f"! {url} : {exc}", file=sys.stderr)
            continue
        print(json.dumps(e, ensure_ascii=False))
        evenements.append(e)
    if not evenements:
        raise RuntimeError("Aucune page d'événement lisible : fichier précédent conservé")
    SORTIE.write_text(json.dumps({
        "updated": datetime.datetime.now(PARIS).isoformat(timespec="minutes"),
        "source": PAGE_ORGA,
        "evenements": evenements,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(evenements)} événements HelloAsso enregistrés")


if __name__ == "__main__":
    main()
