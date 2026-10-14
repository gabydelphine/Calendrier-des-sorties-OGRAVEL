#!/usr/bin/env python3
"""Génère ogravel.ics depuis events.json (sorties sans horaire = journées entières)."""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import hashlib

BASE = Path(__file__).resolve().parent

def echapper(valeur):
    return str(valeur or '').replace('\\', '\\\\').replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;')

def plier(ligne):
    # RFC 5545 : maximum 75 octets par ligne physique, continuation par espace.
    lignes, courant = [], ''
    for caractere in ligne:
        limite = 75 if not lignes else 74
        if len((courant + caractere).encode('utf-8')) > limite:
            lignes.append(courant)
            courant = caractere
        else:
            courant += caractere
    lignes.append(courant)
    return '\r\n '.join(lignes)

def main():
    data = json.loads((BASE / 'events.json').read_text(encoding='utf-8'))
    horodatage = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lignes = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//OGravel//Calendrier sorties//FR',
              'CALSCALE:GREGORIAN','METHOD:PUBLISH','X-WR-CALNAME:ÔGravel — Prochaines sorties',
              'X-WR-CALDESC:Sorties officielles ÔGravel. Horaires communiqués par l’association.',
              'REFRESH-INTERVAL;VALUE=DURATION:PT12H','X-PUBLISHED-TTL:PT12H']
    for event in data.get('events', []):
        debut = date.fromisoformat(event['date'])
        fin = debut + timedelta(days=1)
        titre = event.get('title','Sortie ÔGravel')
        lieu = event.get('location','')
        cle = f'{debut.isoformat()}|{titre}|{lieu}'
        uid = hashlib.sha256(cle.encode('utf-8')).hexdigest()[:24] + '@ogravel.com'
        lignes += ['BEGIN:VEVENT',f'UID:{uid}',f'DTSTAMP:{horodatage}',
                   f'DTSTART;VALUE=DATE:{debut:%Y%m%d}',f'DTEND;VALUE=DATE:{fin:%Y%m%d}',
                   f'SUMMARY:{echapper(titre)}',f'LOCATION:{echapper(lieu)}',
                   'DESCRIPTION:Horaires et précisions communiqués par l’association ÔGravel.\\nhttps://ogravel.com/calendrier/',
                   'URL:https://ogravel.com/calendrier/','END:VEVENT']
    lignes.append('END:VCALENDAR')
    (BASE / 'ogravel.ics').write_bytes(('\r\n'.join(plier(l) for l in lignes)+'\r\n').encode('utf-8'))
    print(f'ogravel.ics généré : {len(data.get("events", []))} sorties')

if __name__ == '__main__':
    main()
