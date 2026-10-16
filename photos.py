"""Récupère les photos de l'album Google Photos partagé d'ÔGravel.

Lit la page publique de l'album (le lien de partage indiqué dans
app/config.json, clé photos_url) et écrit app/photos.json avec les adresses
des photos, pour le carrousel de l'onglet Photos de l'appli.
En cas d'échec, le fichier précédent est conservé.
"""
import datetime
import json
import re
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "app" / "config.json"
SORTIE = BASE / "app" / "photos.json"
MAXI = 40  # nombre de photos gardées pour le carrousel


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
        photos.append({"url": url, "largeur": largeur, "hauteur": hauteur})
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

    SORTIE.write_text(json.dumps({
        "updated": datetime.date.today().isoformat(),
        "album": album,
        "photos": photos[:MAXI],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
