#!/usr/bin/env python3
"""Génère ogravel.ics depuis events.json (sorties sans horaire = journées entières)."""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import hashlib
import re
import unicodedata

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

def simplifier(texte):
    texte = unicodedata.normalize('NFD', str(texte or ''))
    texte = ''.join(c for c in texte if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9#]+', ' ', texte).strip()

def billet(event, liste):
    """Événement HelloAsso correspondant : même date (ou comprise dedans), sinon même titre."""
    for h in liste:
        if h.get('date') and h['date'] <= event['date'] <= (h.get('end_date') or h['date']):
            return h
    for h in liste:
        if simplifier(h.get('titre')) and simplifier(h.get('titre')) == simplifier(event.get('title')):
            return h
    return None

def main():
    data = json.loads((BASE / 'events.json').read_text(encoding='utf-8'))
    try:
        liste = json.loads((BASE / 'helloasso.json').read_text(encoding='utf-8')).get('evenements', [])
    except (OSError, ValueError):
        liste = []
    events = list(data.get('events', []))
    # Événements HelloAsso absents du calendrier ogravel.com (ex. Occitanie 600).
    aujourdhui = date.today().isoformat()
    for h in liste:
        if h.get('date') and (h.get('end_date') or h['date']) >= aujourdhui \
                and not any(billet(e, liste) is h for e in events):
            events.append({'date': h['date'], 'end_date': h.get('end_date'), 'title': h.get('titre', ''), 'location': ''})
    events.sort(key=lambda e: e['date'])
    horodatage = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lignes = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//OGravel//Calendrier sorties//FR',
              'CALSCALE:GREGORIAN','METHOD:PUBLISH','X-WR-CALNAME:ÔGravel — Prochaines sorties',
              'X-WR-CALDESC:Sorties officielles ÔGravel. Horaires communiqués par l’association.',
              'REFRESH-INTERVAL;VALUE=DURATION:PT12H','X-PUBLISHED-TTL:PT12H']
    for event in events:
        debut = date.fromisoformat(event['date'])
        # Sorties sur plusieurs jours (week-end) : DTEND est exclusif en iCalendar.
        dernier = date.fromisoformat(event['end_date']) if event.get('end_date') else debut
        fin = max(dernier, debut) + timedelta(days=1)
        titre = event.get('title') or 'Sortie ÔGravel'
        lieu = event.get('location','')
        cle = f'{debut.isoformat()}|{titre}|{lieu}'
        h = billet(event, liste)
        url = 'https://ogravel.com/calendrier/'
        description = 'Horaires et précisions communiqués par l’association ÔGravel.\\nhttps://ogravel.com/calendrier/'
        if h:
            url = h.get('url') or url
            if h.get('etat') == 'cloture':
                titre += ' (complet)' if h.get('raison') == 'complet' else ' (inscriptions clôturées)'
                description = 'Inscriptions clôturées.\\n' + url
            else:
                description = 'Inscription sur HelloAsso' + (f" ({h['prix']})" if h.get('prix') else '') + ' :\\n' + url
        uid = hashlib.sha256(cle.encode('utf-8')).hexdigest()[:24] + '@ogravel.com'
        lignes += ['BEGIN:VEVENT',f'UID:{uid}',f'DTSTAMP:{horodatage}',
                   f'DTSTART;VALUE=DATE:{debut:%Y%m%d}',f'DTEND;VALUE=DATE:{fin:%Y%m%d}',
                   f'SUMMARY:{echapper(titre)}',f'LOCATION:{echapper(lieu)}',
                   f'DESCRIPTION:{description}',
                   f'URL:{url}','END:VEVENT']
    lignes.append('END:VCALENDAR')
    (BASE / 'ogravel.ics').write_bytes(('\r\n'.join(plier(l) for l in lignes)+'\r\n').encode('utf-8'))
    print(f'ogravel.ics généré : {len(events)} sorties')

if __name__ == '__main__':
    main()
