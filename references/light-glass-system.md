# Surface and Theme System — Light, Glass, and Parity

> The filename is kept for compatibility. This module covers **light, dark, and
> glass**, not one exclusive theme. Every value here is a **PRESET** from
> `design-tokens.css`; the authority remains the project's `DESIGN.md`.

The standard for designing light themes, glassmorphism, and design systems in
`kuron-design-figcraft` (`.figcraft` and UI implementations). For live editing,
use `live-editing-workflow.md`; for execution rules, `dark-artifact-rules.md`.

---

## 1. Visual Philosophy: Eye Comfort and Zero AI Slop

1. **Anti-glare for long sessions.** The preset canvas uses a warm `--ks-bg`
   (not pure white across the whole screen). The area behind the page uses
   `--ks-raised` so panels keep a soft separator. Projects may replace these
   values in `DESIGN.md` — what matters is surface hierarchy, not a specific
   colour.
2. **Quiet vibrancy.** Frosted glass is **only** for floating chrome/navigation/
   inspectors — never over text or reading areas. The `editorial` and
   `clean_utility` directions may use no glass at all
   (see `style-directions.md`).
3. **Zero AI slop.**
   - No uniform gradients, neon glow, or dense black shadows.
   - **One protagonist per screen:** exactly one `action-primary` action above
     the fold.
   - **Reader-friendly:** plain labels naming action + object, no unexplained
     jargon (`copy_tone` in `DESIGN.md`).
   - **Clear separation:** original vs result vs active (`action-primary` 2px)
     vs technical data (`data-technical` mono + `tabular-nums`) readable within
     three seconds.

---

## 2. Colour System = Roles, Not Hex

Read the `dark`/`light` pairs directly from the `DESIGN.md` block
`tokens.semantic.color` (resolver described in that document §3). The tables
below are only a **map of roles plus bundled preset values** for recognition.

### A. Surfaces, lines, text

| Role | CSS alias | Light preset | Dark preset | Function |
|---|---|---|---|---|
| `bg` | `--ks-bg` | `#F7F6F4` | `#0D0D10` | App canvas |
| `surface` | `--ks-surface` | `#FFFFFF` | `#141418` | Main panel / solid card |
| `surface-2` | `--ks-surface-2` | `#F1F0ED` | `#1A1A20` | Header, toolbar, rail |
| `raised` | `--ks-raised` | `#E8E7E3` | `#22222A` | Elevated card/panel |
| `hover` | `--ks-hover` | `#DEDDD8` | `#2A2A33` | Transient hover state |
| `selected` | `--ks-selected` | `#D8D7D1` | `#34343F` | Persistent selection |
| `line` | `--ks-line` | `#DFDFD9` | `#26262E` | 1px hairline |
| `line-strong` | `--ks-line-strong` | `#C4C3BC` | `#35353F` | Window/dialog contour |
| `ring` | `--ks-ring` | `#55555F` | `#9A9AA8` | Focus ring (not decoration) |
| `text` | `--ks-text` | `#16161A` | `#ECECF1` | Primary text |
| `text-2` | `--ks-text-2` | `#55555F` | `#A5A6B0` | Secondary text |
| `text-3` | `--ks-text-3` | `#7C7C86` | `#71727D` | Placeholder, inactive text |

### B. Accent and status

| Role | Light preset | Dark preset | Use |
|---|---|---|---|
| `action-primary` | `#C4342A` | `#FF6B5A` | **One** main action; hover/fg/soft follow the role |
| `data-technical` | `#0B6E78` | `#35E7F5` | Technical data only, mono + `.tnum` |
| `status-success` | `#1F7A4D` | `#5FD99A` | Complete, online |
| `status-warn` | `#8A5A00` | `#FFC15E` | In progress, needs review |
| `status-danger` | `#B3261E` | `#FF5C5C` | Destructive action, error |
| `status-info` | `#1F5FBF` | `#6BA6FF` | Neutral information |

These values are **not mandatory**. `action-primary` may be blue, purple, or
green; `data-technical` may be orange or grey. What is mandatory: stable roles,
passing contrast, and soft tints derived from tokens.

### C. Glass (optional by direction)

| Role | Light preset | Dark preset | Use |
|---|---|---|---|
| `glass-bg` | `rgba(255,255,255,0.72)` | `rgba(34,34,42,0.72)` | Main frosted panel |
| `glass-toolbar` | `rgba(241,240,237,0.78)` | `rgba(26,26,32,0.78)` | Window bar, toolbar |
| `glass-floating` | `rgba(255,255,255,0.88)` | `rgba(42,42,51,0.88)` | Popover, dropdown, dialog |
| `glass-specular` | `rgba(255,255,255,0.70)` | `rgba(255,255,255,0.14)` | 1px highlight |
| `glass-border` | `rgba(22,22,26,0.08)` | `rgba(236,236,241,0.10)` | Outer glass border |
| `glass-shadow` | soft diffuse | soft diffuse | macOS-like depth; dense black shadow forbidden |

> **Mandatory representation in `.figcraft` when glass is used:** `effect.add`
> with `"type": "glass"` (depth ≈20–26, frost ≈8–12, refraction ≈0.85–0.94,
> dispersion ≈0.35–0.45, lightAngle -45, specular stroke, soft drop shadow) —
> **not** a flat transparent fill. Add an ambient backdrop behind the panel so
> refraction is actually visible. These numbers are native-effect presets, not
> brand colours.

---

## 3. Iconography (Lucide)

- One consistent library (Lucide), **no emoji** as UI icons.
- 24×24 grid, 1.75px stroke (1.5px at 14px), round cap/join,
  `stroke="currentColor"`.
- Preset sizes: `14` (badge/meta), `16` (button/input), `20` (toolbar/rail),
  `24` (dialog heading, empty state). Take values from `component`/`semantic.type`.
- Icon colour follows roles: default `text-2`, active `text`/`action-primary`,
  technical `data-technical`, status `status-*`.

---

## 4. Typography, Spacing, Radius, Elevation

- Typography and spacing **always come from `DESIGN.md`** (`semantic.type`,
  `semantic.space`). The preset in `design-tokens.css` is only a starting point.
- Radius uses `control / card / window / pill`.
- Elevation is **at most 3 levels** (`component.elevation.maxLevels`):
  hairline → raised glass → floating glass. A fourth level is forbidden.

---

## 5. Components and States

All components use Auto-Layout and support `default`, `hover`, `focus` (`ring`
2px, offset 2px), `disabled` (`opacity: 0.45`), plus `empty`, `loading`, `error`,
and `success` per `DESIGN.md`. Build base components first, then
**duplicate → refine**.

| Component | Anatomy (preset sizes) | Variants and states |
|---|---|---|
| Button | `sm/md/lg` from `component.button.height`; `control` radius; `space.xxs` gap | Primary (`action-primary`), Secondary (`surface` + `line-strong`), Ghost, Danger |
| Input / Dropdown | `component.field.height`; `control` radius; `space.sm` padding | Default, Focus (`ring`), Error (`danger` + cause & solution) |
| Badge / Chip | `component.badge.height`; `pill` radius; no border | ok / warn / danger / info / technical on matching soft tints |
| Segmented | height of `button.sm/md`; `surface-2` + `line` | Active item `surface` + elevation 1 |
| Slider | `line-strong` track; `action-primary`/`data-technical` fill; 14px thumb | Always paired with a mono `.tnum` value label |
| Colour swatch | 24×24, `control` radius | Active = 2px `action-primary` ring, offset 2px |
| Mini toolbar | `glass-floating` + specular + shadow; `card` radius | Font, Size, Colour, Duplicate, Delete |
| Glass card | `glass-bg`; `card` radius; `space.sm`–`space.md` padding | Project, sidebar, inspector |
| Modal dialog | `glass-floating`; `card` radius; diffuse scrim | One primary CTA + ghost Cancel; `Esc` closes |

### Modal Dialog Note

1. **Scrim** covers the screen frame with no extra blur (the dialog already has
   glass).
2. **Dialog surface** uses `glass-floating` + native glass effect, `card` radius,
   maximum width `component.dialog.maxWidthPx`, elevation 3.
3. **Header:** `type.heading` title + ghost `Close` button (no accent).
4. **Body:** one concrete consequence sentence + fields if needed; errors give
   cause + way out, not just a code.
5. **Footer:** exactly one `action-primary` CTA + ghost `Cancel`. Two primary
   CTAs are forbidden.
6. **Behaviour:** `Esc` closes the topmost layer; initial focus on title/first
   field; focus stays inside until closed; on close, focus returns to the trigger.

Decorative illustrations, gradients, and dense shadows inside the dialog are
forbidden.

---

## 6. Checklist Before Claiming Done

1. `DESIGN.md` exists, the JSON block is valid, and theme/direction are readable.
2. Glass is only on chrome/navigation/inspectors — never over reading areas (or
   absent entirely when the direction calls for no glass).
3. Exactly one `action-primary` CTA above the fold.
4. `data-technical` only for technical mono data + `.tnum`.
5. No emoji icons; icons use a consistent 24-grid library.
6. Badges/chips have no border and use the correct soft tint.
7. Spacing and radius use only the ladders from `DESIGN.md`.
8. Maximum three elevation levels; visible 2px `ring` focus; `opacity: 0.45`
   for disabled.
9. Dialog has one primary CTA, `Esc` closes, focus stays inside.
10. Original vs result vs active vs technical text is distinguishable in 3 seconds.
11. Contrast meets `a11y.minContrast` (AA/AAA) in both themes.
12. Lint has 0 warnings **and** the exported PNG was opened pixel by pixel.
13. Light/dark parity passes (§7) for every token used.

---

## 7. Light/Dark Parity

1. **Every light token has a dark counterpart** in `DESIGN.md`. A token without
   a pair is a parity defect.
2. **One role = one token.** Do not invent a per-screen "selected" colour.
3. **Tints are token-derived:** `color-mix(in srgb, var(--token) N%, transparent)`.
4. **Text/layer contrast is at least AA** (or AAA when `a11y.minContrast =
   "AAA"`) in both themes. Preset values meet AA, but projects must re-measure
   after changing colours.
5. **`action-primary` may change value across themes**, but its role stays the
   main action. The same applies to `data-technical`.
6. **Status colours must read in both themes**; if contrast drops, fix the token
   pair rather than overwriting with an arbitrary hex value.
7. **Test parity with the ambient backdrop:** light glass needs a warm backdrop,
   dark glass needs layered surfaces. Without it the glass effect looks flat.

---

## 8. Conclusion

Dark and light share the same builder contract, linter, and 3–5x verification
loop (`dark-artifact-rules.md`). Only token values, style direction, glass
representation, and the checklist above change. Package version: `3.1.0`.
