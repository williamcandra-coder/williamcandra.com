# williamcandra.com

A retro pixel-art arcade — a personal website styled as an 80s/90s arcade room.
Each cabinet on the homepage opens a playable browser game. Built as a plain
static site (no framework, no build step) so it runs on any OS and browser and
deploys straight to GitHub Pages.

**Live:** https://williamcandra.com

---

## Current status

- **v1.4.0** — Homepage (`index.html`) plus three playable games: **RAGE WINGS**
  (`rage-wings.html`), **Snake** (`snake.html`), and **Breakout** (`breakout.html`).
- **Minesweeper** (`minesweeper.html`) isn't built yet — its cabinet link shows
  the on-brand `404.html` until it ships. See `CHANGELOG.md` for the roadmap.

---

## Project structure

```
/
├── index.html        # Homepage — the arcade room
├── 404.html          # On-brand "cabinet out of order" fallback
├── rage-wings.html   # RAGE WINGS — one-tap flappy-style game
├── snake.html        # Snake
├── breakout.html     # Breakout rage game
├── minesweeper.html  # (planned) max-difficulty minesweeper — cabinet 404s for now
├── CNAME             # Custom domain for GitHub Pages (williamcandra.com)
├── .gitignore
├── CHANGELOG.md      # Version history (semantic versioning)
└── README.md
```

Every page is a **self-contained** HTML file — its CSS and JS live inline in the
same file. There is no shared stylesheet or bundler. This keeps each game
independent and the whole site build-free.

---
