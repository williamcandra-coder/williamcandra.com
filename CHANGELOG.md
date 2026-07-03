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
