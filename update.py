import json, re, urllib.request, datetime, html
from bs4 import BeautifulSoup
from pathlib import Path
URL='https://ogravel.com/calendrier/'
MONTHS={'janvier':1,'février':2,'fevrier':2,'mars':3,'avril':4,'mai':5,'juin':6,'juillet':7,'août':8,'aout':8,'septembre':9,'octobre':10,'novembre':11,'décembre':12,'decembre':12}
PAT=re.compile(r'^(\d{1,2})(?:\s*[-–]\s*\d{1,2}(?:\s*[-–]\s*\d{1,2})?)?\s+('+'|'.join(MONTHS)+r')(?:\s+(20\d{2}))?$',re.I)
now=datetime.date.today()
req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 ÔGravel Calendar Summary'})
with urllib.request.urlopen(req,timeout=30) as response: soup=BeautifulSoup(response.read(),'html.parser')
# The member appointments are presented as consecutive text blocks in the calendar section.
heading=next((h for h in soup.find_all(re.compile('^h[1-6]$')) if 'Les RDV des membres' in h.get_text(' ',strip=True)),None)
if not heading: raise RuntimeError('Section Les RDV des membres introuvable : vérifier le site')
parts=[]
for element in heading.next_elements:
    if getattr(element,'name',None) in ('h1','h2') and element is not heading: break
    if getattr(element,'name',None) in ('p','h3','h4','h5','h6'):
        value=element.get_text(' ',strip=True)
        if value and (not parts or parts[-1]!=value): parts.append(value)
# Fallback to section text separated by lines if WordPress blocks are not standard paragraphs.
if not any(PAT.match(x) for x in parts):
    txt=heading.parent.get_text('\n',strip=True) if heading.parent else ''
    parts=[s.strip() for s in txt.splitlines() if s.strip()]
events=[]
for i,s in enumerate(parts):
    m=PAT.match(s)
    if not m: continue
    day,month,year=int(m.group(1)),MONTHS[m.group(2).lower()],int(m.group(3) or now.year)
    try: dt=datetime.date(year,month,day)
    except ValueError: continue
    if dt<now: continue
    following=[]
    for v in parts[i+1:]:
        if PAT.match(v): break
        if v not in following: following.append(v)
        if len(following)>=3: break
    # Convention on the source page: date, location, event title, details.
    location=following[0] if following else ''
    title=following[1] if len(following)>1 else (following[0] if following else 'Sortie ÔGravel')
    events.append({'date':dt.isoformat(),'title':title,'location':location})
# Highlight event from Grand Events section when a precise date is available.
intro=soup.get_text(' ',strip=True)
for match in re.finditer(r'Ô Gravel Surprise ride #\d+\s+(\d{1,2})\s+('+'|'.join(MONTHS)+r')\s+(20\d{2})',intro,re.I):
    dt=datetime.date(int(match.group(3)),MONTHS[match.group(2).lower()],int(match.group(1)))
    if dt>=now: events.append({'date':dt.isoformat(),'title':match.group(0).split(' '+match.group(1))[0],'location':''})
events=sorted({(e['date'],e['title']):e for e in events}.values(),key=lambda x:(x['date'],x['title']))
if not events: raise RuntimeError('Aucun événement futur détecté : la page ne sera pas remplacée par une liste vide')
Path(__file__).with_name('events.json').write_text(json.dumps({'updated':now.isoformat(),'source':URL,'events':events},ensure_ascii=False,indent=2),encoding='utf-8')
print('Événements futurs :',len(events))
