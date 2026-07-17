# Workyard Ops — Spaceship UI Design

**Date:** 2026-07-17  
**Repo:** workyard (standalone Workyard API dashboard)  
**Branch:** `feature/spaceship-ui`  
**Status:** Implementation design (locked aesthetic)

## Goal

Restyle the entire Workyard Ops dashboard as an **Apple Park / WWDC spaceship HUD** — deep black void, cool silver-blue glass, mono typography, ambient starfield — while keeping every existing JS data flow, API call, and Final Assembly camera path intact.

## Locked decisions

| Decision | Choice |
|----------|--------|
| Aesthetic | Spaceship HUD (dark void + silver-blue). No light-mode toggle on this branch. |
| Coverage | Everywhere: Overview, Browse, Final Assembly, Calendar, Explorer, Console, drawer, mobile shell |
| Implementation | In-file CSS + small JS in `templates/dashboard.html` only — no new npm deps |
| Camera overlay (`#sf-camera`) | Mostly leave as-is (already black); sync accent tokens only if needed |
| Out of scope | Backend/`app.py`/`client.py`, new features, Three.js |

## Visual system

### Palette (CSS variables)

| Token | Value | Role |
|-------|-------|------|
| `--bg` | `#05060a` | Void background |
| `--panel` | `rgba(255,255,255,0.04)` | Elevated glass |
| `--ink` | `#e8eef7` | Primary text |
| `--muted` | `#8b95a8` | Secondary text |
| `--line` | `rgba(255,255,255,0.10)` | Hairline borders |
| `--accent` | `#8ec5ff` | Silver-blue chrome / active |
| `--accent-soft` | `rgba(142,197,255,0.12)` | Soft wash |
| `--live` | `#e05d00` | Hardman orange — rare live signal only (on-the-clock pulse, `/OPS` spark) |
| `--ok` / `--warn` / `--err` | Retuned greens / ambers / reds for dark contrast |

### Typography

- **Space Grotesk** — brand, headings, toolbar titles
- **IBM Plex Mono** — data cells, nav labels, ASCII glyphs, drawer keys
- Drop system-ui as the hero stack

### Atmosphere (fixed behind `.layout`, `pointer-events: none`)

1. Slow radial **gradient mesh** (cool blues, `@keyframes` drift)
2. Canvas **starfield** (sparse dots + very slow parallax)
3. Optional faint **orbital grid** behind Overview only (low opacity)

On small screens, starfield opacity is dialed down. Under `prefers-reduced-motion: reduce`: freeze mesh/starfield/ASCII on frame 0; disable view-enter and pulse expansions.

## Motion language (intentional, not noise)

1. **Starfield + gradient drift** — continuous ambient presence
2. **ASCII nav icon frame cycle** (~400–600ms) — glyph prefix on every `.navbtn`; active nav brighter + shimmer
3. **View enter** — short opacity/translate on section swaps via `switchView` / `show*` helpers

Also: Overview stat cards fade-up on load; table row hover = soft blue wash; drawer slide retuned for dark glass shadow.

## ASCII nav map

Static views and dynamic resource buttons share a key→glyph map, e.g.:

| Key | Frames (example) |
|-----|------------------|
| overview | `◈` `◇` `◆` `◇` |
| calendar | `▣` `▤` `▥` `▤` |
| final-assembly | `◎` `◉` `●` `◉` |
| explorer / console | `⌬` / `⌘`-style mono frames |
| employees, projects, … | per-resource glyph sequences |

Resource buttons built in `initNav()` get icons from the same map.

## Structural touchpoints

All changes live in `templates/dashboard.html`:

- `:root` + global CSS → dark token swap; glass cards/buttons/inputs/tables
- `body` → atmosphere wrappers before `.layout`
- `nav` / `.brand` / `.navbtn` → glass rail, ASCII prefixes, active silver-blue
- Overview / calendar / FA / explorer / console → inherit tokens; polish chips, pills, method badges
- `#drawer`, mobile bar, hamburger → dark glass
- JS: hook transition class in `switchView`; inject ASCII in `initNav`; starfield + icon ticker at boot

## Success criteria

- First viewport reads as a spaceship HUD, not a cream admin panel
- Every view shares the dark glass shell + starfield
- ASCII nav icons visibly animate; freeze under reduced motion
- Tables/forms remain readable and touch-usable on phone
- No regressions to API calls, submissions, or camera flows
