# Motion stack

**Sources:** `source:motion-primitives`, `source:animate-ui`, `source:our-skill`  
**Provenance ids:** `motion.hero-entrance`, `motion.section-reveal`, `motion.animate-ui-opt-in`, `motion.no-stack`

## Default policy

1. Prefer **static, clear UI** first (shadcn primitives).
2. Add **one** intentional motion moment per page when it helps hierarchy (usually a hero entrance).
3. Optionally add **one** secondary dealt moment (section reveal), not a circus of animations.
4. **Do not stack** Animate UI + Motion Primitives + flashy 21st motion on the same surface by default (`motion.no-stack`).
5. Always respect `prefers-reduced-motion` (static fallbacks).

## Motion Primitives (`source:motion-primitives`)

- Repo: https://github.com/ibelick/motion-primitives
- Docs: https://motion-primitives.com/docs
- Use for: hero entrance, text/image reveals, spotlight moments on marketing or product showcases.
- Tag: `motion.hero-entrance` / `motion.section-reveal` in `decision.md` and `agents.md`.

## Animate UI (`source:animate-ui`)

- Repo: https://github.com/imskyleen/animate-ui
- Use to animate **existing** shadcn/Radix primitives after the user asks for motion on controls.
- CLI: `npx @animate-ui/cli@latest animate all` (or per-component).
- Tag: `motion.animate-ui-opt-in`.
- Do **not** auto-animate form inputs, checkboxes, or dense data tables unless requested.

## With 21st / Taste Skill / Impeccable

- If a 21st section already includes strong motion, skip adding Motion Primitives on top.
- Taste Skill may deal hero entrance + 1–2 moments — treat those as the motion budget.
- Impeccable `animate` / `delight` / `overdrive` are steer commands after a draft exists; still honor the no-stack rule and reduced motion.
