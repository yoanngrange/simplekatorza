#!/usr/bin/env python3
"""
Scraper Katorza — récupère la programmation depuis cinefil.com,
télécharge les affiches localement dans ./posters/ et génère programme.json
consommable par index.html.

Basé sur les microdata Schema.org (ScreeningEvent / Movie / Person) que cinefil
maintient pour le SEO Google Rich Results — format quasi immuable.

Usage :
    pip install requests beautifulsoup4
    python scraper.py
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SOURCE_URL = "https://www.cinefil.com/cinema/le-katorza-nantes/programmation"
KATORZA_BILLETTERIE_URL = "https://www.katorza.fr/katorza/alaffiche/katorza"
ROOT = Path(__file__).parent
OUTPUT_JSON = ROOT / "programme.json"
POSTERS_DIR = ROOT / "posters"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
IMG_HEADERS = {**HEADERS, "Referer": "https://www.cinefil.com/"}


# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------

@dataclass
class Seance:
    date: str
    time: str
    version: str


@dataclass
class Film:
    title: str
    year: Optional[int] = None
    duration_min: Optional[int] = None
    genre: Optional[str] = None
    directors: list[str] = field(default_factory=list)
    cast: list[str] = field(default_factory=list)
    synopsis: str = ""
    poster_url: Optional[str] = None
    detail_url: Optional[str] = None
    seances: list[Seance] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["seances"] = [asdict(s) for s in self.seances]
        return d


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

ISO_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?", re.IGNORECASE)
TIME_RE = re.compile(r"\b(\d{1,2})[:hH](\d{2})\b")
ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def clean_text(el) -> str:
    if el is None:
        return ""
    if isinstance(el, str):
        return re.sub(r"\s+", " ", el).strip()
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def parse_iso_duration(iso: str) -> Optional[int]:
    """'PT85M' → 85 ; 'PT1H25M' → 85"""
    if not iso:
        return None
    m = ISO_DURATION_RE.fullmatch(iso.strip())
    if not m:
        return None
    h = int(m.group(1) or 0)
    mm = int(m.group(2) or 0)
    total = h * 60 + mm
    return total or None


def parse_year_from_date(iso_date: str) -> Optional[int]:
    """'2026-06-17' → 2026"""
    m = ISO_DATE_RE.match(iso_date or "")
    return int(m.group(1)) if m else None


def fetch_page(url: str) -> str:
    print(f"→ Fetch {url}", file=sys.stderr)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def download_poster(remote_url: str) -> Optional[str]:
    if not remote_url:
        return None
    filename = remote_url.split("?")[0].rsplit("/", 1)[-1]
    if not filename or "." not in filename:
        return None
    local_path = POSTERS_DIR / filename
    rel_path = f"posters/{filename}"

    if local_path.exists() and local_path.stat().st_size > 0:
        return rel_path

    urls_to_try = [remote_url]
    if "?" in remote_url:
        urls_to_try.append(remote_url.split("?")[0])
    else:
        urls_to_try.append(remote_url + "?class=posterlg")

    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=IMG_HEADERS, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 1024:
                POSTERS_DIR.mkdir(exist_ok=True)
                local_path.write_bytes(resp.content)
                print(f"  ↓ {filename} ({len(resp.content) // 1024} KB)", file=sys.stderr)
                return rel_path
        except requests.RequestException as exc:
            print(f"  ⚠︎ {filename} : {exc}", file=sys.stderr)
    print(f"  ⚠︎ {filename} : échec téléchargement", file=sys.stderr)
    return None


def find_film_blocks(soup: BeautifulSoup) -> list[Tag]:
    """Chaque film = <li itemtype="https://schema.org/ScreeningEvent">."""
    return soup.select('li[itemtype*="ScreeningEvent"]')


def extract_persons(container: Tag) -> list[str]:
    """
    Extrait les personnes taggées <span itemprop="director" itemscope>
    dans un container donné (peut être .realisateurpos ou .actorpos).
    Cinefil met acteurs ET réalisateurs sous itemprop="director" (bug de balisage),
    on discrimine donc par le container CSS parent, pas par l'attribut.
    """
    names = []
    for span in container.select('span[itemprop="director"], span[itemprop="actor"]'):
        name_el = span.select_one('[itemprop="name"]')
        name = clean_text(name_el) if name_el else clean_text(span)
        if name:
            names.append(name)
    # Dédoublonne en préservant l'ordre
    seen = set()
    result = []
    for n in names:
        if n not in seen:
            seen.add(n)
            result.append(n)
    return result


def parse_seances(li: Tag) -> list[Seance]:
    """
    Extrait les séances d'un <li ScreeningEvent>.

    Structure cinefil :
    - Boutons `.dayselector[data-date][data-day="Samedi"]` : 7 dates ISO.
    - Pour chaque jour, un tabpanel `.tab-pane.lesseances.Samedi` contient les séances.
    - Chaque séance : <button> avec <span class="seance-time">16:05</span>
      et <span class="seance-langue">VF</span>.
    - Bouton "Aucune séance" n'a pas de `.seance-time`, il est ignoré naturellement.
    """
    seances: list[Seance] = []
    horaires = li.select_one(".horaires")
    if not horaires:
        return []

    # Map jour (Samedi, Dimanche, ...) → date ISO (2026-07-04, ...)
    day_to_date: dict[str, str] = {}
    for btn in horaires.select(".dayselector[data-date][data-day]"):
        day = (btn.get("data-day") or "").strip()
        d = (btn.get("data-date") or "").strip()
        if day and d and ISO_DATE_RE.match(d):
            day_to_date[day] = d

    for day, iso_date in day_to_date.items():
        # Le tabpanel des séances porte les classes .tab-pane.lesseances.[Jour]
        panel = horaires.select_one(f".lesseances.{day}")
        if not panel:
            continue
        for btn in panel.select("button"):
            time_el = btn.select_one(".seance-time")
            if not time_el:
                continue  # bouton "Aucune séance" n'a pas de .seance-time
            m = TIME_RE.search(clean_text(time_el))
            if not m:
                continue
            h, mm = int(m.group(1)), int(m.group(2))
            if not (0 <= h <= 23 and 0 <= mm <= 59):
                continue

            v_el = btn.select_one(".seance-langue")
            version = clean_text(v_el) if v_el else ""
            if version in ("VOSTFR", "VOST"):
                version = "VO"

            seances.append(Seance(
                date=iso_date,
                time=f"{h:02d}:{mm:02d}",
                version=version,
            ))

    return sorted(seances, key=lambda s: (s.date, s.time))


def parse_film(li: Tag) -> Optional[Film]:
    # Titre
    title_el = li.select_one('h3[itemprop="name"] a, h3[itemprop="name"]')
    if not title_el:
        # Fallback : meta itemprop="name"
        meta = li.select_one('meta[itemprop="name"]')
        title = meta.get("content", "").strip() if meta else ""
    else:
        title = clean_text(title_el)
    if not title:
        return None

    film = Film(title=title)

    # URL fiche film
    url_el = li.select_one('h3[itemprop="name"] a[href]')
    if url_el:
        film.detail_url = url_el.get("href", "")

    # Année (depuis datePublished)
    dp = li.select_one('meta[itemprop="datePublished"]')
    if dp:
        film.year = parse_year_from_date(dp.get("content", ""))

    # Durée
    dur = li.select_one('meta[itemprop="duration"]')
    if dur:
        film.duration_min = parse_iso_duration(dur.get("content", ""))

    # Genre
    genre_el = li.select_one('[itemprop="genre"]')
    if genre_el:
        film.genre = clean_text(genre_el)

    # Poster
    img = li.select_one('img[itemprop="image"]')
    if img:
        remote = img.get("src") or img.get("data-src") or ""
        if remote:
            film.poster_url = download_poster(remote)

    # Réalisateurs (container .realisateurpos)
    realiser_cont = li.select_one(".realisateurpos")
    if realiser_cont:
        film.directors = extract_persons(realiser_cont)

    # Casting (container .actorpos)
    actor_cont = li.select_one(".actorpos")
    if actor_cont:
        film.cast = extract_persons(actor_cont)

    # Synopsis
    syn_el = li.select_one('[itemprop="description"], .Synopsis-infos')
    if syn_el:
        film.synopsis = clean_text(syn_el)

    # Séances
    film.seances = parse_seances(li)

    return film


# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------

def main() -> int:
    html = fetch_page(SOURCE_URL)
    soup = BeautifulSoup(html, "html.parser")
    blocks = find_film_blocks(soup)
    print(f"→ {len(blocks)} bloc(s) film détecté(s)", file=sys.stderr)

    films: list[Film] = []
    for b in blocks:
        try:
            f = parse_film(b)
            if f and f.title:
                films.append(f)
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠︎ parse error : {exc}", file=sys.stderr)

    def sort_key(f: Film) -> str:
        t = f.title.lower()
        for prefix in ("le ", "la ", "les ", "l'", "un ", "une ", "des "):
            if t.startswith(prefix):
                return t[len(prefix):]
        return t

    films.sort(key=sort_key)

    output = {
        "cinema": {
            "name": "Katorza",
            "city": "Nantes",
            "address": "3 rue Corneille, 44000 Nantes",
            "billetterie_url": KATORZA_BILLETTERIE_URL,
        },
        "source": SOURCE_URL,
        "scraped_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "films": [f.to_dict() for f in films],
    }

    OUTPUT_JSON.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total_seances = sum(len(f.seances) for f in films)
    with_posters = sum(1 for f in films if f.poster_url)
    print(f"✓ {len(films)} film(s), {total_seances} séance(s), "
          f"{with_posters}/{len(films)} affiche(s) → {OUTPUT_JSON}", file=sys.stderr)

    # Petit résumé par film pour vérif
    for f in films[:3]:
        print(f"  · {f.title} ({f.year}, {f.duration_min}min, {f.genre}) "
              f"— {len(f.seances)} séance(s)", file=sys.stderr)
    if len(films) > 3:
        print(f"  · … ({len(films) - 3} autres)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
