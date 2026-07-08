#!/bin/bash
# update.sh — scrape la programmation Katorza et pousse les changements sur GitHub.
# Conçu pour tourner en cron local (voir crontab plus bas), car cinefil.com
# bloque les requêtes venant des IP des runners GitHub Actions.
#
# Usage manuel :
#   ./update.sh
#
# Logs écrits dans update.log à côté de ce script.

set -euo pipefail

# Se place dans le dossier du script, quel que soit l'endroit d'où cron l'appelle
cd "$(dirname "${BASH_SOURCE[0]}")"

LOG_FILE="update.log"
exec >> "$LOG_FILE" 2>&1

echo ""
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="

# Active le venv
if [ ! -d ".venv" ]; then
    echo "✗ .venv introuvable — lance d'abord : python3 -m venv .venv && source .venv/bin/activate && pip install requests beautifulsoup4"
    exit 1
fi
source .venv/bin/activate

# Scrape
echo "→ Scraping…"
python3 scraper.py
# scraper.py sort avec un code non-nul si 0 films trouvés (voir garde-fou
# interne) — grâce à `set -e` en haut de ce script, l'exécution s'arrête ici
# automatiquement et rien n'est commité si le scrape a échoué.

# Double vérification indépendante : le nombre de films dans programme.json
# doit être raisonnable avant tout commit. Filet de sécurité si jamais le
# garde-fou de scraper.py était un jour contourné ou modifié par erreur.
FILM_COUNT=$(python3 -c "import json; print(len(json.load(open('programme.json'))['films']))" 2>/dev/null || echo "0")
echo "→ $FILM_COUNT film(s) dans programme.json"
if [ "$FILM_COUNT" -lt 5 ]; then
    echo "✗ Trop peu de films ($FILM_COUNT) — abandon, rien n'est commité."
    exit 1
fi

# Commit + push seulement s'il y a des changements
if git diff --quiet programme.json posters/ 2>/dev/null && [ -z "$(git status --porcelain posters/ 2>/dev/null)" ]; then
    echo "→ Aucun changement, rien à commit"
else
    echo "→ Changements détectés, commit + push"
    git add programme.json posters/
    git commit -m "MAJ programme $(date '+%Y-%m-%d')"
    git push
    echo "✓ Poussé sur GitHub"
fi

echo "=== Terminé ==="
