"""Distances et dénivelés annoncés dans le descriptif d'une sortie ÔGravel.

Règles (demandées par le club) :
- « 20-30 km » est UN choix (une fourchette) ; « 20 ou 30 km », « 60/75 km »,
  « 60 km, 90 km » font plusieurs choix ;
- « deux distances 75 - 100 km » : le tiret sépare alors deux choix ;
- le D+ annoncé est rattaché à la distance qu'il suit (ou qu'il précède : « Challenge D+ 2000 m : 93 km ») ;
- chaque distance prend le type (Family, Special, Challenge) écrit juste avant ;
- les kilomètres « en commun », « aller », ou d'un aller/retour facultatif ne sont pas des parcours ;
- sans distance écrite : un choix par type cité (Family, Special), sinon aucun ;
- « Family » ne vaut que pour la distance qui le suit ;
- mots clés (pour les mails) : hors Family, la plus longue distance est « Long », la plus
  courte « Court », celles du milieu « Moyen » (2 choix : Long et Court ; 1 choix : aucun).
"""
import re

NUM = r"\d+(?:[.,]\d+)?"
RE_MENTION = re.compile(
    rf"(?<![\d.,])({NUM}(?:\s*(?:[-–/]|\bou\b|,)\s*{NUM})*)\s*km\b(?:\s*km\b)?", re.I)
RE_TYPE = re.compile(r"\b(family|special|challenge)\b", re.I)
RE_PLUSIEURS = re.compile(r"\b(?:deux|2|trois|3|quatre|4)\s+(?:distances|circuits|parcours|boucles)\b", re.I)
RE_EXCLU_APRES = re.compile(r"^\s*(?:km\s*)?(?:en\s+commun|communs?|aller\b|par\s+le|de\s+liaison)", re.I)
RE_EXCLU_AVANT = re.compile(r"(?:retour|aller)\s+possible|en\s+option|liaison|bivouac", re.I)
RE_DPLUS_APRES = [
    re.compile(r"^[^\n]{0,90}?\bD\s*\+\s*:?\s*(\d[\d\s.]*?)\s*m\b", re.I),
    re.compile(r"^[^\n]{0,25}?\+\s*(\d[\d\s.]*?)\s*m\b", re.I),
    re.compile(r"^[^\n]{0,30}?\b(\d[\d\s.]*?)\s*m\s+de\s+D\s*\+", re.I),
    # « 90km 900D+ », « 58 km (600 m D+) »
    re.compile(r"^\s*[:(\-–]?\s*(\d[\d\s.]*?)\s*m?\s*D\s*\+", re.I),
]
RE_DPLUS_AVANT = re.compile(r"\bD\s*\+\s*:?\s*(\d[\d\s.]*?)\s*m\b[^\n]*$", re.I)


def _km(v):
    v = v.strip().replace(".", ",")
    if "," in v:
        v = v.rstrip("0").rstrip(",")
    return v


def _dplus(v):
    return re.sub(r"[\s.]", "", v)


def _type(texte, pos, debut=0):
    """Type écrit avant la distance. « Family » ne compte que s'il est juste devant
    (après la distance précédente) : « family 20 km, 90 km » → seul 20 km est Family."""
    trouves = [t for t in RE_TYPE.finditer(texte, 0, pos)
               if t.group(1).lower() != "family" or t.start() >= debut]
    return trouves[-1].group(1).capitalize() if trouves else ""


def _valeur(km):
    """Premier nombre d'une distance (« 20-30 » → 20) pour classer les choix."""
    try:
        return float(re.split(r"-", km)[0].replace(",", "."))
    except ValueError:
        return 0.0


def ajouter_niveaux(choix):
    """Mots clés Long / Moyen / Court (hors Family), de la plus longue à la plus courte."""
    autres = sorted([c for c in choix if c.get("km") and c.get("type") != "Family"],
                    key=lambda c: -_valeur(c["km"]))
    if len(autres) >= 2:
        for i, c in enumerate(autres):
            c["niveau"] = "Long" if i == 0 else "Court" if i == len(autres) - 1 else "Moyen"
    return choix


def extraire_parcours(titre, description):
    texte = (titre or "") + "\n" + (description or "")
    mentions = []
    for m in RE_MENTION.finditer(texte):
        apres = texte[m.end():m.end() + 30]
        if RE_EXCLU_APRES.match(apres):
            continue
        debut_phrase = max(texte.rfind("\n", 0, m.start()), texte.rfind(".", 0, m.start() - 1),
                           texte.rfind("/", 0, m.start() - 1) if texte[m.start() - 2:m.start()].strip() == "" else -1)
        avant = texte[max(0, m.start() - 70):m.start()]
        if RE_EXCLU_AVANT.search(texte[debut_phrase + 1:m.start()]) or re.search(r"\(\s*$", avant) and RE_EXCLU_APRES.match(apres or ""):
            continue
        # « 19,87 km aller », « (21,69 km en commun) » déjà écartés ; les heures « 9h » ne sont pas des km.
        mentions.append(m)

    choix = []
    for i, m in enumerate(mentions):
        brut = m.group(1)
        avant = texte[max(0, m.start() - 60):m.start()]
        separateurs = r"\s*(?:/|\bou\b|,(?=\s))\s*"
        if RE_PLUSIEURS.search(avant):
            separateurs = r"\s*(?:/|\bou\b|,(?=\s)|[-–])\s*"
        # « 39,74 » : la virgule décimale n'est jamais un séparateur (pas d'espace après).
        valeurs = [v for v in re.split(separateurs, brut, flags=re.I) if v.strip()]
        fin_fenetre = mentions[i + 1].start() if i + 1 < len(mentions) else len(texte)
        suite = texte[m.end():min(fin_fenetre, m.end() + 120)]
        dplus = None
        if len(valeurs) == 1:
            for r in RE_DPLUS_APRES:
                d = r.search(suite)
                if d:
                    dplus = _dplus(d.group(1))
                    break
            if not dplus:
                ligne = texte[texte.rfind("\n", 0, m.start()) + 1:m.start()]
                d = RE_DPLUS_AVANT.search(ligne)
                if d:
                    dplus = _dplus(d.group(1))
        sorte = _type(texte, m.start(), mentions[i - 1].end() if i else 0)
        for v in valeurs:
            km = "-".join(_km(x) for x in re.split(r"\s*[-–]\s*", v))
            c = {"type": sorte, "km": km}
            if dplus and len(valeurs) == 1:
                c["dplus"] = dplus
            if c not in choix:
                choix.append(c)
    if choix:
        # Type manquant (« 2 circuits : 53 km… ») : on reprend celui du titre, sinon rien.
        return ajouter_niveaux(choix)
    types = []
    for t in RE_TYPE.findall(texte):
        t = t.capitalize()
        if t != "Challenge" and t not in types:
            types.append(t)
    return [{"type": t} for t in types]


def libelle(c):
    """« Court – Special 58 km · D+ 1081 m » ; « Family 20 km » ; « Family » sans distance."""
    morceaux = [c.get("type") or ("Parcours" if not c.get("km") else "")]
    if c.get("niveau"):
        morceaux.insert(0, c["niveau"] + " –")
    if c.get("km"):
        morceaux.append(c["km"] + " km")
    texte = " ".join(x for x in morceaux if x)
    if c.get("dplus"):
        texte += " · D+ " + c["dplus"] + " m"
    return texte
