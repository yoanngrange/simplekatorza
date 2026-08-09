#!/bin/bash
# update.sh — scrape la programmation Katorza et pousse les changements sur GitHub.
# Conçu pour tourner en cron local très fréquemment (toutes les 30 min, voir
# crontab plus bas), car cinefil.com bloque les requêtes venant des IP des
# runners GitHub Actions — il faut donc une IP résidentielle.
#
# Logique de rattrapage : ce script ne fait un vrai scrape que si aucune mise
# à jour n'a réussi depuis le dernier mercredi. Tant qu'aucun run n'a réussi
# cette semaine, chaque exécution retente ; dès qu'un run réussit, tous les
# suivants deviennent des no-op silencieux jusqu'au mercredi suivant.
#
# Usage manuel :
#   ./update.sh

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$(dirname "${BASH_SOURCE[0]}")"

MARKER_FILE=".last_successful_update"
LOG_FILE="update.log"

DOW=$(date +%u)
if [ "$DOW" -ge 3 ]; then
    DAYS_SINCE_WED=$((DOW - 3))
else
    DAYS_SINCE_WED=$((DOW + 4))
fi
LAST_WEDNESDAY=$(date -v-"${DAYS_SINCE_WED}"d +%Y-%m-%d 2>/dev/null || date -d "-${DAYS_SINCE_WED} days" +%Y-%m-%d)

LAST_SUCCESS=$(cat "$MARKER_FILE" 2>/dev/null || echo "1970-01-01")

if [[ "$LAST_SUCCESS" > "$LAST_WEDNESDAY" || "$LAST_SUCCESS" == "$LAST_WEDNESDAY" ]]; then
    exit 0
fi

exec >> "$LOG_FILE" 2>&1

echo ""
echo "=== $(date '+%Y-%m-%d %H:%M:%S') (dernier succès: $LAST_SUCCESS, dernier mercredi: $LAST_WEDNESDAY) ==="

if [ ! -d ".venv" ]; then
    echo "✗ .venv introuvable"
    exit 1
fi
source .venv/bin/activate

echo "→ Scraping…"
python3 scraper.py

FILM_COUNT=$(python3 -c "import json; print(len(json.load(open('programme.json'))['films']))" 2>/dev/null || echo "0")
echo "→ $FILM_COUNT film(s) dans programme.json"
if [ "$FILM_COUNT" -lt 5 ]; then
    echo "✗ Trop peu de films ($FILM_COUNT) — abandon. Nouvel essai dans 30 min."
    exit 1
fi

if git diff --quiet programme.json posters/ 2>/dev/null && [ -z "$(git status --porcelain posters/ 2>/dev/null)" ]; then
    echo "→ Aucun changement, rien à commit"
else
    echo "→ Changements détectés, commit + push"
    git add programme.json posters/
    git commit -m "MAJ programme $(date '+%Y-%m-%d')"
    git push
    echo "✓ Poussé sur GitHub"
fi

date +%Y-%m-%d > "$MARKER_FILE"
echo "✓ Marqueur mis à jour ($(cat "$MARKER_FILE"))"
echo "=== Terminé ==="
