# Changelog

All notable changes to williamcandra.com are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(`MAJOR.MINOR.PATCH`):

- **MAJOR** — big, breaking redesigns or restructures of the whole site.
- **MINOR** — a new game or page added, or a significant new feature.
- **PATCH** — bug fixes, small tweaks, copy changes, style adjustments.

## [Unreleased]

### Planned
- `pinball.html` — retro pinball game (flagship).
- `breakout.html` — a hard, complex Breakout.
- `minesweeper.html` — classic Minesweeper at maximum difficulty.
- `snake.html` — Snake game (already prototyped, to be added to repo).
- "Do Not Ask the Goh Pok Tong" fortune-telling machine — page + concept TBD.
- "Do Not Enter" door — About page as a retro RPG character screen.

## [1.3.1] — 2026-07-04

### Changed
- Shrank the "AFTER HOURS" header font-size clamp and forced it onto a single
  line (`white-space:nowrap`) so it no longer touches the screen edges or wraps
  on small phones.

## [1.3.0] — 2026-07-04

### Added
- Built **Snake** (`snake.html`) — a fully responsive pixel-art snake game: the
  canvas scales to fit with no horizontal overflow from 320px to 1440px, in an
  amber CRT palette matching the site. Swipe + on-screen d-pad touch controls
  plus keyboard (arrows/WASD, Space to pause, Enter to restart), local
  best-score saving, and an EVACUATE back link.

## [1.2.0] — 2026-07-04

### Added
- Added **BREAKOUT** (`breakout.html`) — a one-thumb pixel-art rage game: tap to
  smash office monsters and app-parody creatures, fill the RAGE meter to unleash
  a screen-clearing overload, and climb 50 levels with boss floors. Features
  amber goop splats and randomized K.O. stamps.

## [1.1.0] — 2026-07-03

### Changed
- Committed the page to a warm amber CRT arcade palette (marquee, neon strip,
  UI text) while keeping the individual cabinet screen colors (pinball pink,
  snake teal, breakout gold, minesweeper red) — warm frame, colorful screens.
- Rebuilt responsiveness as mobile-first with real breakpoints keyed to device
  CSS viewports: 1 column by default (phones, tested at 360/390px), 2 columns
  at ≥ 600px (tablet/iPad portrait), roomier 2-column spacing at ≥ 1024px, and
  at ≥ 1200px the room is capped (~1000px) and centered with the "AFTER HOURS"
  title held to ~34–38px. Added the missing viewport meta tag so phones get the
  mobile layout instead of a shrunk desktop one.

## [1.0.1] — 2026-07-03

### Changed
- Replaced the neon two-tone "WILLIAM CANDRA" header with an amber early-80s
  LCD-style "AFTER HOURS" title: single arcade-amber color (#FFC857), softer
  glow, subtle 12s warm-up flicker (disabled under `prefers-reduced-motion`),
  and a faint CRT scanline overlay confined to the title.

## [1.0.0] — 2026-07-03

### Added
- Initial homepage (`index.html`): the retro arcade room.
  - Neon "WILLIAM CANDRA" sign with flicker animation.
  - Night-time window with animated city skyline (skyscrapers, lit windows,
    blinking beacon, twinkling stars, glowing moon).
  - Arcade floor with six cabinets on a 2-column, 3-row grid:
    - Row 1: Pinball, Snake
    - Row 2: Breakout, Minesweeper
    - Row 3: Do Not Ask the Goh Pok Tong, Do Not Enter
  - Game cabinets link to their pages (`pinball.html`, `snake.html`,
    `breakout.html`, `minesweeper.html`); pages built in later releases.
  - Fortune machine and door marked "COMING SOON" with matching
    "DO NOT ASK" / "DO NOT ENTER" ribbon badges.
  - Hover glow/lift micro-interactions on cabinets.
  - Responsive layout with `clamp()` type scaling.
- On-brand `404.html` ("Cabinet Out of Order") so unbuilt game links fail gracefully.
- `CNAME` for the custom domain `williamcandra.com`.
- `.gitignore` for common OS/editor files.
