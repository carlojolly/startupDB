# Accessibility + responsive review

**Source:** `source:our-skill` (+ amplifiers from Impeccable / Taste Skill)  
**Provenance:** `a11y.baseline`

Run before UI definition of done.

## Accessibility

- [ ] Visible **focus** styles (`focus-visible`); logical tab order
- [ ] Text contrast sufficient against backgrounds (especially on glass / gradients)
- [ ] Hit targets large enough on touch (≥ 44×44 CSS px where practical)
- [ ] Semantic landmarks / headings in order; no skipped levels without reason
- [ ] Images have alt text (or empty alt if decorative)
- [ ] Forms have labels; errors announced accessibly
- [ ] Honor **`prefers-reduced-motion`** — motion has a static fallback
- [ ] Do not convey meaning by color alone

## Responsive

- [ ] First viewport works on ~390px width without horizontal scroll
- [ ] Stacking order matches reading priority on small screens
- [ ] Nav collapses or remains usable; CTAs remain reachable
- [ ] Tables / dashboards have a mobile strategy (stack, scroll, or summary)
- [ ] Type scales remain readable; no clipped headlines

## Companion amplifiers (when installed)

- Impeccable: `/impeccable audit` and `npx impeccable detect <url>` for contrast/tiny text on rendered pages (`impeccable.audit` / `impeccable.detect`).
- Taste Skill: browser checker across 1440 / 1024 / 768 / 390 (`taste.browser-gate`).
- Optional: `21st skills install` then `21st-ui-review` if the user has installed official 21st skills.
