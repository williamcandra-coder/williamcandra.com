# williamcandra.com

A retro pixel-art arcade — a personal website styled as an 80s/90s arcade room.
Each cabinet on the homepage opens a playable browser game. Built as a plain
static site (no framework, no build step) so it runs on any OS and browser and
deploys straight to GitHub Pages.

**Live:** https://williamcandra.com

---

## Current status

- **v1.0.0** — Homepage (`index.html`) is complete and deployable.
- Game pages (`pinball.html`, `snake.html`, `breakout.html`, `minesweeper.html`)
  are **not built yet**. Their cabinet links are live but will show the
  on-brand `404.html` until each game ships. See `CHANGELOG.md` for the roadmap.

---

## Project structure

```
/
├── index.html        # Homepage — the arcade room (v1.0.0)
├── 404.html          # On-brand "cabinet out of order" fallback
├── pinball.html      # (planned) retro pinball
├── snake.html        # (planned) snake
├── breakout.html     # (planned) hard breakout
├── minesweeper.html  # (planned) max-difficulty minesweeper
├── CNAME             # Custom domain for GitHub Pages (williamcandra.com)
├── .gitignore
├── CHANGELOG.md      # Version history (semantic versioning)
└── README.md
```

Every page is a **self-contained** HTML file — its CSS and JS live inline in the
same file. There is no shared stylesheet or bundler. This keeps each game
independent and the whole site build-free.

---
