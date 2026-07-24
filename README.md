# williamcandra.com

**After Hours** — a retro pixel-art arcade and fortune machine. The homepage is a
CRT-styled arcade menu; each entry opens a self-contained browser game or the
Goh Pok Tong fortune machine. Built as a plain static site (no framework, no
build step) so it runs on any OS and browser and deploys straight to GitHub Pages.

**Live:** https://williamcandra.com

---

## Current status

- **v1.5.0** — After Hours homepage (`index.html`) plus four live experiences:
  - **RAGE WINGS** (`rage-wings.html`) — one-tap flap game, v6.6, six playable
    characters each with its own world and physics.
  - **SNAKE** (`snake.html`) — classic crawl.
  - **BREAKOUT** (`breakout.html`) — one-thumb rage game.
  - **GOH POK TONG** (`goh-pok-tong.html`) — Bazi fortune machine (real engine +
    optional Google Sheet storage).
- **Minesweeper** is on the roadmap but not built yet; the homepage no longer
  links to it. See `CHANGELOG.md` for the full history and roadmap.

---

## Project structure

```
/
├── index.html          # Homepage — the After Hours arcade menu
├── 404.html            # On-brand "cabinet out of order" fallback
├── rage-wings.html     # RAGE WINGS — one-tap flap game (v6.6, six characters)
├── snake.html          # Snake
├── breakout.html       # Breakout rage game
├── goh-pok-tong.html   # Goh Pok Tong — Bazi fortune machine
├── bazi-engine.min.js  # Bazi calculation engine (loaded by goh-pok-tong.html)
├── CNAME               # Custom domain for GitHub Pages (williamcandra.com)
├── .gitignore
├── CHANGELOG.md        # Version history (semantic versioning)
└── README.md
```

Each page is a **self-contained** HTML file — its CSS and JS live inline in the
same file — with one exception: `goh-pok-tong.html` loads the shared
`bazi-engine.min.js`. There is no bundler or build step, which keeps each game
independent and the whole site build-free.

---
