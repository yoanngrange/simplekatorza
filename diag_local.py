#!/usr/bin/env python3
"""
Diagnostic — capture le HTML brut reçu par `requests` en local, pour le
comparer à ce qu'un vrai navigateur reçoit. Écrit local_response.html
et affiche un résumé.

Usage :
    python3 diag_local.py
"""

import requests

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

print(f"Status code : {resp.status_code}")
print(f"Content-Length header : {resp.headers.get('Content-Length', 'absent')}")
print(f"Content-Type : {resp.headers.get('Content-Type', 'absent')}")
print(f"Server : {resp.headers.get('Server', 'absent')}")
print(f"Taille réelle reçue : {len(resp.text):,} caractères")
print()

# Sauve le HTML brut
with open("local_response.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
print("→ HTML sauvé dans local_response.html")
print()

# Quelques vérifs rapides
checks = {
    "ScreeningEvent (attendu)": "ScreeningEvent" in resp.text,
    "Jim Queen (titre attendu)": "Jim Queen" in resp.text,
    "cloudflare": "cloudflare" in resp.text.lower(),
    "captcha": "captcha" in resp.text.lower(),
    "challenge": "challenge" in resp.text.lower(),
    "just a moment": "just a moment" in resp.text.lower(),
    "access denied": "access denied" in resp.text.lower(),
    "blocked": "blocked" in resp.text.lower(),
}

print("Vérifications de contenu :")
for label, found in checks.items():
    marker = "✓" if found else "✗"
    print(f"  {marker} {label}")

print()
print("→ Colle-moi tout ce qui est au-dessus, et si possible les 50")
print("  premières lignes de local_response.html :")
print("  head -n 50 local_response.html")
