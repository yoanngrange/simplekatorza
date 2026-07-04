#!/usr/bin/env python3
"""
Diagnostic — inspecte le HTML réel de cinefil pour voir pourquoi le scraper
principal ne trouve pas les films. Écrit page.html + diag.txt à côté.
"""
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path

URL = "https://www.cinefil.com/cinema/le-katorza-nantes/programmation"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

resp = requests.get(URL, headers=HEADERS, timeout=30)
resp.raise_for_status()
resp.encoding = resp.apparent_encoding or "utf-8"
html = resp.text

# Sauve le HTML brut pour inspection
Path("page.html").write_text(html, encoding="utf-8")
print(f"→ page.html sauvé ({len(html):,} chars)")

soup = BeautifulSoup(html, "html.parser")

# --- Diagnostic 1 : liens vers /film/
film_links = soup.select('a[href^="/film/"]')
print(f"\n[1] Liens '/film/...' trouvés : {len(film_links)}")
for a in film_links[:5]:
    print(f"    href={a.get('href')!r}  parent={a.parent.name if a.parent else None}")

# --- Diagnostic 2 : liens vers /film/ dans un h2 ou h3
in_heading = [a for a in film_links if a.find_parent(["h2", "h3"])]
print(f"\n[2] Liens '/film/...' dans h2/h3 : {len(in_heading)}")
for a in in_heading[:3]:
    h = a.find_parent(["h2", "h3"])
    print(f"    <{h.name}> classes={h.get('class')} texte={a.get_text(strip=True)!r}")

# --- Diagnostic 3 : liens vers /film/ dans un h1..h6
for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
    n = len([a for a in film_links if a.find_parent(tag)])
    if n:
        print(f"    dans <{tag}> : {n}")

# --- Diagnostic 4 : images de films
imgs_movies = soup.select('img[src*="/movies/"]')
imgs_data_src = soup.select('img[data-src*="/movies/"]')
imgs_srcset = [i for i in soup.find_all('img') if i.get('srcset') and '/movies/' in i.get('srcset', '')]
print(f"\n[3] Images :")
print(f"    src*=/movies/ : {len(imgs_movies)}")
print(f"    data-src*=/movies/ : {len(imgs_data_src)}")
print(f"    srcset avec /movies/ : {len(imgs_srcset)}")
if imgs_movies:
    print(f"    ex src : {imgs_movies[0].get('src')!r}")
if imgs_data_src:
    print(f"    ex data-src : {imgs_data_src[0].get('data-src')!r}")

# --- Diagnostic 5 : où sont les affiches ? (attributs d'image)
print(f"\n[4] Attributs des 3 premières <img> ayant '/movies/' dans un attr :")
count = 0
for img in soup.find_all("img"):
    attrs = dict(img.attrs)
    if any("/movies/" in str(v) for v in attrs.values()):
        print(f"    #{count} : {attrs}")
        count += 1
        if count >= 3:
            break

# --- Diagnostic 6 : structure autour du premier heading de film
if in_heading:
    a = in_heading[0]
    print(f"\n[5] Chaîne de parents du premier titre de film :")
    node = a
    for i in range(8):
        if node is None:
            break
        cls = " ".join(node.get('class', [])) if hasattr(node, 'get') else ""
        name = getattr(node, 'name', '?')
        print(f"    [{i}] <{name}> class={cls!r}")
        node = node.parent

# --- Diagnostic 7 : essai d'autres motifs de container
print(f"\n[6] Recherche d'autres containers possibles :")
for sel in ["article", "li.film", "div.film", ".movie-item", ".seances-cinema-item",
            "div[class*='film']", "div[class*='seance']", "li[class*='film']",
            "tr[class*='film']", "section[class*='film']"]:
    els = soup.select(sel)
    if els:
        print(f"    {sel!r} : {len(els)} match(es)")

# --- Diagnostic 8 : détection heures
times_found = len(re.findall(r"\b\d{1,2}[:hH]\d{2}\b", html))
print(f"\n[7] Occurrences 'HH:MM' dans le HTML : {times_found}")

# --- Diagnostic 9 : détection en-têtes de jour
day_headers = re.findall(
    r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+(Lun\.|Mar\.|Mer\.|Jeu\.|Ven\.|Sam\.|Dim\.)",
    html,
)
print(f"[8] En-têtes de jour type 'Samedi Sam.' : {len(day_headers)}")

print("\n→ Colle-moi tout ce qui est au-dessus + les 200 premières lignes de page.html")
print("   head -n 200 page.html")
