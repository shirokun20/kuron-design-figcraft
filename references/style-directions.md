# Dynamic Style Directions — Four Presets, Not One Uniform

This module ensures the skill **does not lock a single style**. The design
direction is chosen from the domain and the user's decision, then **written to
the project's `DESIGN.md`** through the `style_direction` key. The presets here
are only starting points: they may be blended, modified, or replaced by
`custom`, as long as the result stays recorded in `DESIGN.md`.

Colour, spacing, radius, type, and state rules **always** come from the
project's `DESIGN.md` (see `DESIGN.md` and `token-architecture.md`). This module
only describes the *character* of each direction and which *token levers* to set.

---

## 1. Gate before choosing

Run the four-question brief (`product-designer-2026.md`), then offer 2-3
sensible directions. The user chooses or steers. Record the result:

- `style_direction`: one of the IDs below, or `custom`.
- `style_notes`: the blend, exceptions, and rationale.
- `locale` + `copy_tone`: the project's microcopy voice.

Choosing a direction merely because it is the "skill default" is forbidden.
Silence must not be read as approval of a preset.

---

## 2. Four presets

| ID | Best for | Distinctive character | Primary token levers | Anti-pattern |
|---|---|---|---|---|
| `dense_operational` | professional flows, dense data, fast decisions | compact rows, 3 columns, dense tables, actions next to data | small `semantic.space.*`; concise `type.body`; `component.button.height` md; firm `line`/`line-strong` | decorative whitespace, competing CTAs, blurred hierarchy |
| `bento_modular` | multi-module dashboards, summaries, portals | asymmetric card grid, clear module scale, elevation 2-3 | larger `radius.card`/`radius.window`; distinguish `raised` from `surface`; `space.lg` between cards | every card the same size, excessive shadows, a different colour per card |
| `editorial` | content, documentation, long reading | typographic rhythm, measured reading width, minimal decoration | larger `type.body`/`type.display`; looser `space.md`–`space.xl`; `measure` ≈60-75ch; warm `bg` | overlong lines, small fonts, glass over text |
| `clean_utility` | narrow tools, setup, forms, wizards | one focus, minimal decoration, one main column | conservative `space`; `elevation.maxLevels` 1-2; consistent `component.field.height`; strong focus `ring` | multiple CTAs, nested panels, unexplained jargon |

`custom` is used when a project is genuinely distinctive. Still fill in
`style_notes` and map every role — do not delete a role just because it is
unused.

---

## 3. Colour roles are universal; their values are not

In every direction the following roles **always exist** (see `DESIGN.md` §3):

| Role | Function | Any colour allowed? |
|---|---|---|
| `action-primary` | one primary action per screen | Yes — as long as contrast with `action-primary-fg` satisfies `a11y` |
| `data-technical` | coordinates, IDs, counters (mono + `tnum`) | Yes — as long as it is distinct from body text |
| `status-success/warn/danger/info` | status | Yes — as long as it reads in both themes and never relies on colour alone |
| `bg` / `surface` / `raised` | surface hierarchy | Yes — as long as elevation order stays 1-3 |

> Coral/red and cyan in the bundled preset are **historical examples**, not the
> skill's identity. A project may use blue, green, purple, or neutrals as long
> as roles and contrast are preserved. Never write a hex value directly in a
> builder.

---

## 4. Style lever → `DESIGN.md` change (examples)

| Desire | Change in the JSON block |
|---|---|
| "More room for reading" | raise `primitive.type.body` and `semantic.space.md`, and add `measure` in `style_notes` |
| "Softer/thicker cards" | change `semantic.radius.card`, distinguish `raised` from `surface` |
| "Denser table" | lower `semantic.space.xs`, align `component.button.height.md` with the row |
| "Blue accent, not red" | replace `primitive.color.brand*` (dark + light), leave the `action-primary` role as is |
| "No glassmorphism" | still define `glass-*` tokens, but `editorial`/`clean_utility` may not use them |
| "AAA contrast target" | set `a11y.minContrast = "AAA"` and fix the `text`/`bg` pair until it passes |

Every change above must be reverified with the 3-5x PNG loop — a token change
is a visual change.

---

## 5. Non-negotiable dynamic rules

1. **One protagonist per screen**, regardless of the `action-primary` colour.
2. **Spacing rhythm from `semantic.space`**, never a "looks about right" number.
3. **Three-stroke hierarchy**: title (`display`/`heading`) → body (`body`) →
   metadata (`mono`, `tabular-nums`).
4. **Complete states** per `states` in `DESIGN.md`:
   `default/hover/focus/disabled/empty/loading/error/success`. No hollow screens.
5. **Accessibility binds every direction**: AA/AAA contrast, visible focus,
   touch targets ≥ `a11y.minTouchTargetPx`, reduced motion, never colour alone.
6. **Component-first**: build components first, then `duplicate → refine`
   (`product-designer-2026.md`).
7. **No AI slop**: no uniform gradients, empty decoration, or cliché layouts
   identical across domains. Prioritise *cognitive clarity*.

---

## 6. One-line summary

`domain brief → offer 2-3 directions → choose → write style_direction + tokens
to DESIGN.md → components first → duplicate & refine → complete states → PNG
evidence`.
