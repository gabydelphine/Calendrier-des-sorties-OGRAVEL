import json
import re
import urllib.request
import datetime
from pathlib import Path
from bs4 import BeautifulSoup

URL = "https://ogravel.com/calendrier/"
MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2,
    "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10,
    "novembre": 11, "décembre": 12, "decembre": 12
}
MONTH_RE = "|".join(MONTHS)
DATE_RE = re.compile(
    rf"^(\d{{1,2}})(?:\s*[-–]\s*(\d{{1,2}}))?\s+"
    rf"({MONTH_RE})(?:\s+(20\d{{2}}))?$",
    re.I
)
today = datetime.date.today()

request = urllib.request.Request(
    URL, headers={"User-Agent": "Mozilla/5.0"}
)
with urllib.request.urlopen(request, timeout=30) as response:
    soup = BeautifulSoup(response.read(), "html.parser")

heading = next(
    (h for h in soup.find_all(re.compile(r"^h[1-6]$"))
     if "Les RDV des membres" in h.get_text(" ", strip=True)),
    None
)
if heading is None:
    raise RuntimeError("Section Les RDV des membres introuvable")

parts = []
for element in heading.next_elements:
    if getattr(element, "name", None) in ("h1", "h2") and element is not heading:
        break
    if getattr(element, "name", None) in ("p", "h3", "h4", "h5", "h6"):
        value = element.get_text(" ", strip=True)
        if value and (not parts or parts[-1] != value):
            parts.append(value)

if not any(DATE_RE.match(x) for x in parts):
    txt = heading.parent.get_text("\n", strip=True) if heading.parent else ""
    parts = [s.strip() for s in txt.splitlines() if s.strip()]

events = []
for i, value in enumerate(parts):
    match = DATE_RE.match(value)
    if not match:
        continue

    start_day = int(match.group(1))
    end_day = int(match.group(2) or start_day)
    month = MONTHS[match.group(3).lower()]
    year = int(match.group(4) or today.year)

    if not match.group(4):
        # Pour les dates sans année, on retient la prochaine occurrence.
        while True:
            try:
                end_date = datetime.date(year, month, end_day)
            except ValueError:
                break
            if end_date >= today:
                break
            year += 1

    try:
        start_date = datetime.date(year, month, start_day)
        end_date = datetime.date(year, month, end_day)
    except ValueError:
        continue

    if end_date < start_date or end_date < today:
        continue

    following = []
    for item in parts[i + 1:]:
        if DATE_RE.match(item):
            break
        if item not in following:
            following.append(item)
        if len(following) >= 3:
            break

    location = following[0] if following else ""
    title = following[1] if len(following) > 1 else (
        following[0] if following else "Sortie ÔGravel"
    )

    event = {
        "date": start_date.isoformat(),
        "title": title,
        "location": location
    }
    if end_date != start_date:
        event["end_date"] = end_date.isoformat()
    events.append(event)

text = soup.get_text(" ", strip=True)
surprise_re = re.compile(
    rf"Ô Gravel Surprise ride #\d+\s+(\d{{1,2}})\s+"
    rf"({MONTH_RE})\s+(20\d{{2}})", re.I
)
for match in surprise_re.finditer(text):
    try:
        date = datetime.date(
            int(match.group(3)),
            MONTHS[match.group(2).lower()],
            int(match.group(1))
        )
    except ValueError:
        continue
    if date >= today:
        events.append({
            "date": date.isoformat(),
            "title": match.group(0).split(" " + match.group(1))[0],
            "location": ""
        })

events = sorted(
    {
        (e["date"], e["title"]): e
        for e in events
    }.values(),
    key=lambda e: (e["date"], e["title"])
)

if not events:
    raise RuntimeError(
        "Aucun événement futur détecté : ancien calendrier conservé"
    )

output = {
    "updated": today.isoformat(),
    "source": URL,
    "events": events
}
Path(__file__).with_name("events.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print(f"{len(events)} événements futurs enregistrés")
