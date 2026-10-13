import json
import re
import urllib.request
import datetime
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

request = urllib.request.Request(
    URL, headers={"User-Agent": "Mozilla/5.0"}
)
with urllib.request.urlopen(request, timeout=30) as response:
    soup = BeautifulSoup(response.read(), "html.parser")

lines = [
    line.strip()
    for line in soup.get_text("\n", strip=True).splitlines()
    if line.strip()
]

start = next(
    (i for i, line in enumerate(lines)
     if "Les RDV des membres" in line),
    None
)
if start is None:
    raise RuntimeError("Section des rendez-vous introuvable")

section = lines[start + 1:]
for i, line in enumerate(section):
    if line.startswith("Tous droits réservés"):
        section = section[:i]
        break

# Repérer l'année indiquée dans le calendrier.
explicit_years = [
    int(m.group(3))
    for line in section
    if (m := DATE_PATTERN.fullmatch(line)) and m.group(3)
]
default_year = max(explicit_years) if explicit_years else TODAY.year

events = []
for i, line in enumerate(section):
    match = DATE_PATTERN.fullmatch(line)
    if not match:
        continue

    days = [
        int(value)
        for value in re.split(r"\s*[-–]\s*", match.group(1))
    ]
    month = MONTHS[match.group(2).lower()]
    year = int(match.group(3) or default_year)

    try:
        first = datetime.date(year, month, days[0])
        last = datetime.date(year, month, days[-1])
    except ValueError:
        continue

    if last < first or last < TODAY:
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

    event = {
        "date": first.isoformat(),
        "title": title,
        "location": location
    }
    if last != first:
        event["end_date"] = last.isoformat()
    events.append(event)

# Ajouter les grands événements précisément datés.
text = soup.get_text(" ", strip=True)
surprise = re.compile(
    rf"(Ô Gravel Surprise ride #\d+)\s+"
    rf"(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})",
    re.I
)
for match in surprise.finditer(text):
    try:
        date = datetime.date(
            int(match.group(4)),
            MONTHS[match.group(3).lower()],
            int(match.group(2))
        )
    except ValueError:
        continue
    if date >= TODAY:
        events.append({
            "date": date.isoformat(),
            "title": match.group(1),
            "location": ""
        })

events = sorted(
    {(e["date"], e["title"]): e for e in events}.values(),
    key=lambda e: (e["date"], e["title"])
)

if not events:
    raise RuntimeError(
        "Aucun événement futur détecté : données précédentes conservées"
    )

output = {
    "updated": TODAY.isoformat(),
    "source": URL,
    "events": events
}
Path(__file__).with_name("events.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print(f"{len(events)} événements futurs enregistrés")
