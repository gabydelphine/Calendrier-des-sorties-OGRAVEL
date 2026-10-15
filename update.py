"""Récupère les prochaines sorties du calendrier officiel ÔGravel.

Lit https://ogravel.com/calendrier/ (rubrique « Les RDV des membres » et
grands événements « Surprise ride »), puis écrit events.json.
En cas d'échec, le fichier précédent est conservé.
"""
import datetime
import json
import re
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

URL = "https://ogravel.com/calendrier/"
TODAY = datetime.date.today()

MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2,
    "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10,
    "novembre": 11, "décembre": 12, "decembre": 12
}
MONTH_PATTERN = "|".join(MONTHS)
DATE_PATTERN = re.compile(
    rf"^(\d{{1,2}}(?:\s*[-–]\s*\d{{1,2}})*)\s+"
    rf"({MONTH_PATTERN})(?:\s+(20\d{{2}}))?$",
    re.I
)


def lire_page():
    request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return BeautifulSoup(response.read(), "html.parser")


def annees_par_ordre(dates, today, base=None):
    """Déduit l'année des dates sans année.

    Le calendrier est rangé dans l'ordre chronologique : quand le mois
    recule (décembre puis janvier), on passe à l'année suivante. On part de
    la première année écrite sur la page ; à défaut, de l'année en cours.
    dates : liste de (mois, année écrite ou None).
    """
    ecrites = [annee for _, annee in dates if annee]
    annee = ecrites[0] if ecrites else (base or today.year)
    resultat = []
    mois_precedent = None
    for mois, annee_ecrite in dates:
        if annee_ecrite:
            annee = annee_ecrite
        elif mois_precedent is not None and mois < mois_precedent:
            annee += 1
        resultat.append(annee)
        mois_precedent = mois
    return resultat


def extraire(soup, today=TODAY):
    lines = [
        line.strip()
        for line in soup.get_text("\n", strip=True).splitlines()
        if line.strip()
    ]

    start = next(
        (i for i, line in enumerate(lines) if "Les RDV des membres" in line),
        None
    )
    if start is None:
        raise RuntimeError("Section des rendez-vous introuvable")

    section = lines[start + 1:]
    for i, line in enumerate(section):
        if line.startswith("Tous droits réservés"):
            section = section[:i]
            break

    reperes = [
        (i, m) for i, line in enumerate(section)
        if (m := DATE_PATTERN.fullmatch(line))
    ]
    dates = [(MONTHS[m.group(2).lower()], int(m.group(3)) if m.group(3) else None)
             for _, m in reperes]
    annees = annees_par_ordre(dates, today)
    # Page sans aucune année écrite, mise à jour en fin d'année pour la saison
    # suivante : si tout tombe dans le passé, c'est l'année prochaine.
    if dates and not any(a for _, a in dates):
        derniere = max(
            datetime.date(an, mois, 1) for (mois, _), an in zip(dates, annees)
        )
        if derniere < today.replace(day=1) - datetime.timedelta(days=60):
            annees = annees_par_ordre(dates, today, base=today.year + 1)

    events = []
    for (i, match), year in zip(reperes, annees):
        days = [int(v) for v in re.split(r"\s*[-–]\s*", match.group(1))]
        month = MONTHS[match.group(2).lower()]
        try:
            first = datetime.date(year, month, days[0])
            last = datetime.date(year, month, days[-1])
        except ValueError:
            continue
        if last < first or last < today:
            continue

        following = []
        for value in section[i + 1:]:
            if DATE_PATTERN.fullmatch(value):
                break
            if value not in following:
                following.append(value)
            if len(following) >= 2:
                break

        location = following[0] if following else ""
        title = following[1] if len(following) > 1 else (
            following[0] if following else "Sortie ÔGravel"
        )
        event = {"date": first.isoformat(), "title": title, "location": location}
        if last != first:
            event["end_date"] = last.isoformat()
        events.append(event)

    # Grands événements précisément datés (« Ô Gravel Surprise ride #8 17 octobre 2026 »).
    text = soup.get_text(" ", strip=True)
    surprise = re.compile(
        rf"(Ô Gravel Surprise ride #\d+)\s+"
        rf"(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})",
        re.I
    )
    for match in surprise.finditer(text):
        try:
            date = datetime.date(
                int(match.group(4)), MONTHS[match.group(3).lower()], int(match.group(2))
            )
        except ValueError:
            continue
        if date >= today:
            events.append({"date": date.isoformat(), "title": match.group(1), "location": ""})

    return sorted(
        {(e["date"], e["title"]): e for e in events}.values(),
        key=lambda e: (e["date"], e["title"])
    )


def main():
    events = extraire(lire_page())
    if not events:
        raise RuntimeError("Aucun événement futur détecté : données précédentes conservées")
    output = {"updated": TODAY.isoformat(), "source": URL, "events": events}
    Path(__file__).with_name("events.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(events)} événements futurs enregistrés")


if __name__ == "__main__":
    main()
