# Companion stack

Route work to the right tool. Do not vendor these repos; install and call them.
Every recommendation below is tracked in `provenance.md`.

## Decision tree

1. **New marketing / company site** → Taste Skill (`source:taste-skill`) for screen plan + browser gate; then 21st for sections; then Impeccable polish.
2. **App screens / dashboards** → shadcn/ui (`source:shadcn-ui`) → optional motion → 21st for large blocks → craft checklist → Impeccable.
3. **Iterate existing UI** → Impeccable steer/critique/audit/polish/detect (`source:impeccable`).
4. **Need a section fast** → 21st search/install (`source:21st-dev`), then restyle tokens.
5. **Need motion** → see `motion-stack.md` (`source:motion-primitives`, `source:animate-ui`).

## shadcn/ui

**Source:** `source:shadcn-ui` · https://github.com/shadcn-ui/ui · provenance: `prim.shadcn-base`, `prim.button`, `prim.dialog`, `prim.input`

Default accessible primitive layer (Button, Dialog, Input, etc.). Open code lands in the project.

```bash
npx shadcn@latest init
npx shadcn@latest add button dialog input
```

Tag installed files in `agents.md` Components with the matching provenance id.

## 21st.dev

**Source:** `source:21st-dev` · see `twentyfirst-dev.md` · provenance: `catalog.21st-sections`

Search/install real React/Tailwind sections before inventing. Adapt to project tokens.

## Motion Primitives

**Source:** `source:motion-primitives` · https://github.com/ibelick/motion-primitives · see `motion-stack.md`

Section/hero motion built with Motion + Tailwind. Docs: https://motion-primitives.com/docs

## Animate UI

**Source:** `source:animate-ui` · https://github.com/imskyleen/animate-ui · see `motion-stack.md`

Animated drop-ins for Radix / Base UI / React Aria — swap imports on existing shadcn primitives.

```bash
npx @animate-ui/cli@latest animate all
# or animate specific components after shadcn exists
```

Opt-in only (`motion.animate-ui-opt-in`). Do not auto-animate every control.

## Taste Skill

**Source:** `source:taste-skill` · https://github.com/Leonxlnx/taste-skill · skill id `design-taste-frontend`

Install:

```bash
npx skills add https://github.com/Leonxlnx/taste-skill --skill "design-taste-frontend"
```

Use for company/marketing sites: classify business, plan screen-by-screen, one section per desktop viewport, real product UI/photos, browser consistency checker + finish gate. Needs Node 22+ and Chrome/Chromium.

## Impeccable

**Source:** `source:impeccable` · https://github.com/pbakaus/impeccable

Install:

```bash
npx impeccable install --providers=claude,cursor --scope=project
```

Then in agent chat: `/impeccable init`, later `/impeccable document`, and steer with `critique`, `audit`, `polish`, `bolder`, `quieter`, etc.

CLI detector:

```bash
npx impeccable detect src/
npx impeccable detect http://localhost:<port>
```

Keep `PRODUCT.md` / `DESIGN.md` aligned with this pack’s `context.md` (product narrative) after UI approval.

## Our pack

**Source:** `source:our-skill` — inventory, checklist, craft refs, DoD, a11y, provenance, taste-memory, project docs templates.
