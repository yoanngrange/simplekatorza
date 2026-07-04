# SimpleKatorza

App web statique responsive qui affiche la programmation du cinéma Katorza
(Nantes) en se concentrant sur l'essentiel : titre, réalisateur, durée, affiche,
séances. Hébergeable tel quel sur GitHub Pages, mise à jour automatique chaque
mercredi matin via GitHub Actions.

Deux vues :
1. **Programme** — tous les films de la semaine, tri alphabétique naturel
   (« Le / La / Les / L' » ignorés).
2. **Dans moins d'une heure** — séances qui démarrent dans l'heure, triées par
   urgence, compte à rebours qui se rafraîchit toutes les minutes.

## Architecture

```
katorza/
├── index.html                       ← app statique (charge programme.json)
├── programme.json                   ← données (généré par scraper.py)
├── posters/                         ← affiches (téléchargées par scraper.py)
│   └── {id}.webp
├── scraper.py                       ← fetch cinefil + download posters
└── .github/
    └── workflows/
        └── update.yml               ← cron mercredi 9h UTC
```

Tout est statique : GitHub Pages sert les fichiers, aucun runtime,
aucune dépendance externe à l'exécution.

## Setup initial

```bash
# 1. Cloner ce repo
git clone <ton-repo> katorza && cd katorza

# 2. Faire tourner le scraper une première fois (télécharge affiches + JSON)
pip install requests beautifulsoup4
python3 scraper.py

# 3. Tester en local (fetch() nécessite HTTP, pas file://)
python3 -m http.server 8000
open http://localhost:8000
```

## Déploiement GitHub Pages

1. Push le repo sur GitHub (public de préférence — GitHub Actions gratuit sans
   limite sur les repos publics).
2. Settings → Pages → Source : « Deploy from a branch », branche `main`,
   dossier `/` (racine).
3. Settings → Actions → General → Workflow permissions : coche « Read and
   write permissions » (permet au workflow de commit les mises à jour).
4. C'est tout. Le premier commit déclenche Pages, et chaque mercredi 09:00 UTC
   le workflow met à jour `programme.json` + `posters/` en pushant sur `main`.

Tu peux aussi déclencher le workflow manuellement via l'onglet Actions →
« Update programme » → « Run workflow ».

## Comment ça marche

1. **`scraper.py`** parse la page publique
   [cinefil.com/cinema/le-katorza-nantes/programmation](https://www.cinefil.com/cinema/le-katorza-nantes/programmation).
   Cinefil est un site SSR classique (pas de JS à exécuter), donc `requests` +
   `beautifulsoup4` suffisent. Il télécharge aussi chaque affiche localement
   dans `posters/{id}.webp` avec un Referer légitime (idempotent : ne
   re-télécharge pas ce qui existe déjà).
2. **`programme.json`** contient les métadonnées de tous les films de la
   semaine + toutes les séances datées + les chemins locaux vers les affiches.
3. **`index.html`** est 100% statique : il fait un `fetch('programme.json')` au
   chargement et rend les deux vues côté client. Les affiches sont servies
   depuis le repo, aucun appel externe au runtime.

## Sources et pérennité

Le scraper vise cinefil.com et pas katorza.fr parce que :
- **katorza.fr** est une SPA Next.js (données chargées en JS), il faudrait un
  navigateur headless (Playwright) pour scraper → complexité, taille des
  images Docker sur les runners, fragile aux changements de version.
- **cinefil.com** rend le HTML côté serveur, se parse en 5 requêtes HTTP
  simples, format stable depuis longtemps. Cinefil est alimenté par TMDB pour
  les métadonnées films (logo TMDB en pied de page + CDN images3.cinefil.com)
  et par un flux de séances agrégé (probablement type Webedia).

Si un jour cinefil change de structure et casse le scraper, il suffira
d'ajuster les sélecteurs. Le workflow n'écrasera pas `programme.json` si le
scraper échoue (le job GitHub Actions fail visiblement dans l'onglet Actions).

## Limites connues

- **Lien billetterie direct** : chaque bouton horaire pointe vers la page
  Katorza générale (`katorza.fr/katorza/alaffiche/katorza`), pas directement
  vers l'URL VAD de la séance (type `/vad/691/147402/38494`). Ces URLs ne sont
  pas exposées dans cinefil et récupérer les vraies impliquerait de scraper
  katorza.fr en headless, ce qui casse le principe « pérenne + simpliste ».
- **Nationalité** : cinefil ne l'expose pas sur la page d'un cinéma (seulement
  sur la fiche film individuelle). Pourrait être récupérée en suivant chaque
  `detail_url` — au prix de 17 requêtes HTTP supplémentaires par run.
- **Bande-annonce YouTube** : non incluse. cinefil a un lecteur de trailer
  mais l'URL YouTube brute n'est pas exposée en clair.

## Personnalisation

Toutes les couleurs et polices sont en variables CSS en tête de `index.html`
(section `<style>`). Les paramètres du scraper (URL source, dossier posters)
sont en constantes en haut de `scraper.py`.

[![pages-build-deployment](https://github.com/yoanngrange/simplekatorza/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/yoanngrange/simplekatorza/actions/workflows/pages/pages-build-deployment)
