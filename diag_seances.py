#!/usr/bin/env python3
"""
Diagnostic — le scraper trouve 0 séance alors que des films sont détectés.
Isole le bloc <div class="horaires">...</div> du premier film pour voir
précisément la structure HTML actuelle de cinefil.
"""

import requests
from bs4 import BeautifulSoup

URL = "https://www.cinefil.com/cinema/le-katorza-nantes/programmation"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

resp = requests.get(URL, headers=HEADERS, timeout=30)
resp.raise_for_status()
soup = BeautifulSoup(resp.text, "html.parser")

with open("page_seances.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
print(f"→ page_seances.html sauvé ({len(resp.text):,} chars)\n")

films = soup.select('li[itemtype*="ScreeningEvent"]')
print(f"→ {len(films)} film(s) détecté(s)\n")

if not films:
    print("Aucun film trouvé, rien à inspecter.")
    exit()

first = films[0]
slug = first.get("data-movie-slug", "?")
print(f"→ Premier film : {slug}\n")

horaires = first.select_one(".horaires")
if not horaires:
    print("✗ Pas de div.horaires trouvé dans ce film !")
    print("\nClasses présentes dans le <li> :")
    for el in first.find_all(True, class_=True):
        classes = " ".join(el.get("class", []))
        if classes:
            print(f"  <{el.name}> class=\"{classes}\"")
else:
    print("✓ div.horaires trouvé\n")
    print("=" * 60)
    print(str(horaires)[:6000])
    print("=" * 60)

print("\n→ Colle-moi tout ce qui est au-dessus.")
