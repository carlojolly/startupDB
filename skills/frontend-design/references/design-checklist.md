# Design checklist: 20 ways to unslop AI designs

**Source:** `source:user-notes` · provenance: `checklist.unslop-20`, `anti.*`

Run before calling UI done. Mark each item.

## Remove visual clutter

- [ ] **1.** Delete filler badges. (`anti.filler-badges`)
- [ ] **2.** Drop redundant labels.
- [ ] **3.** Unitalicize random words.
- [ ] **4.** Mono only where needed (code, IDs, tabular data).
- [ ] **13.** Remove embellishments that do not carry meaning.

## Establish a consistent visual system

- [ ] **5.** Use a design system (tokens + shared components). Prefer shadcn base (`prim.shadcn-base`).
- [ ] **11.** Add one clear accent colour (tight palette — `craft.tight-palette`).
- [ ] **12.** Keep icons consistent (one family, one stroke weight).
- [ ] **14.** Inner radius = outer radius − padding.
- [ ] **15.** Improve text contrast.
- [ ] **18.** Use tabular numbers for stats and prices.

## Improve hierarchy, layout, and messaging

- [ ] **6.** Show the actual product (`craft.product-in-hero`).
- [ ] **7.** Enlarge the main feature.
- [ ] **8.** Group with spacing (not boxes for everything).
- [ ] **9.** Make headlines specific.
- [ ] **10.** Emphasize the CTA (`craft.cta-hierarchy`).
- [ ] **16.** Wrap headlines properly (no awkward orphans if avoidable).
- [ ] **17.** Align by eye, not only by pixel grid.

## Add useful interaction feedback

- [ ] **19.** Add loading states.
- [ ] **20.** Animate useful feedback only (see `motion-stack.md`).

## Extra anti-slop (from Impeccable vocabulary)

- [ ] Avoid Inter / Roboto / Arial as the only expressive brand face (`anti.inter-everywhere`).
- [ ] Avoid purple-on-white / purple→indigo gradient defaults (`anti.purple-gradient-slop`).
- [ ] Avoid nested cards and card spam in heroes (`anti.nested-cards`).
