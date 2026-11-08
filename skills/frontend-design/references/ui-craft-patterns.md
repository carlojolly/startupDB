# UI craft patterns (quality references)

**Source:** `source:user-mockups` (+ per-brand tags)  
These are **craft references**, not mandatory themes. Extract hierarchy, glass, CTAs, product-in-hero, and palette *discipline*. Never force these brand colors on unrelated projects.

Open images under `../assets/` when designing.

## Shared craft (all mockups)

| Pattern | What to copy | What not to force | Provenance |
|---------|--------------|-------------------|------------|
| Hero composition | One dominant visual plane; brand + one headline + one support line + CTA group | Extra stats/schedules cluttering first viewport unless product needs it | `craft.hero-composition` |
| Tight palette | 3 named colors with clear roles (bg / accent / secondary) | Exact hexes from another brand | `craft.tight-palette` |
| Product in hero | Real UI chrome (timeline, media grid, schedule widget, progress ring) | Abstract blobs as the main idea | `craft.product-in-hero` |
| CTA hierarchy | Solid primary + quieter secondary | Equal-weight twin buttons | `craft.cta-hierarchy` |
| Glass | Frosted panels for widgets/overlays with blur + hairline border | Glass wallpaper on everything | `mock.glass-card` |

## Code XR (dashboard)

**Assets:** `assets/code-xr-dashboard.jpg`, `assets/code-xr-glassy-v24.jpg`  
**Source:** `source:user-mockups:code-xr`  
**Example palette mood:** warm copper / terracotta glass on soft atmosphere (example only).

- Narrow frosted sidebar + modular glass widgets
- Sprint/hero card with progress ring and teammate presence
- Calendar strip + agenda with a clear “Next” emphasis
- KPI row: large tabular figures, trend badge, sparkline (`mock.dashboard-stats`)
- Useful hover lift on stats (e.g. Framer Motion `y: -5`) — one subtle interaction language

## FluxEdit (dark product landing)

**Assets:** `assets/fluxedit-landing.jpg`, `assets/fluxedit-hero-hires.jpg`  
**Source:** `source:user-mockups:fluxedit` · provenance: `mock.fluxedit-dark-hero`  
**Example palette:** Midnight Black `#02070A`, Electric Blue `#0297DE`, Cantaloupe Orange `#FC734D` (example only).

- Dark cinematic hero; serif italic for one emphatic word, sans for the rest
- Central primary CTA as focal point
- Social proof metrics flanking, not dominating
- Bottom row of glass feature previews showing **real editor UI** (media library, color curves, timeline)

## Palmatech (health / lifestyle landing)

**Assets:** `assets/palmatech-landing.jpg`, `assets/palmatech-hero-hires.jpg`  
**Source:** `source:user-mockups:palmatech` · provenance: `mock.palmatech-glass-schedule`  
**Example palette:** Sky Blue `#0593C6`, White `#FCFFFF`, Hot Pink `#D83995` (example only).

- Full-bleed colorful atmosphere behind clear white headline
- Pill nav; solid primary “Try for Free” + secondary “Schedule Demo”
- Glass schedule widget with location + level tags (`mock.palmatech-glass-schedule`)
- Feature strip with short lines — one idea each

## Stack alignment

Prefer implementing these patterns with:

1. shadcn primitives (`prim.*`)
2. 21st sections when a catalog block fits (`catalog.21st-sections`)
3. Motion per `motion-stack.md`
4. Impeccable pass after a draft exists
