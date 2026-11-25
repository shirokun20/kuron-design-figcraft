# Product Designer 2026 — Four Mandatory Pillars

The working standard for `kuron-design-figcraft` as a modern product designer:
understand the domain first, design the whole system (not just a UI skin), build
from components, then execute decisively. This module binds `SKILL.md`,
`DESIGN.md`, `patterns.md`, `style-directions.md`, and the theme modules — it is
not optional material.

The output of pillars 1 and 2 **must be written into the project's `DESIGN.md`**
before the canvas is touched. Without that, the design is not considered
`DESIGN.md`-backed and work must stop.

---

## 1. Domain, Outcome, and Dynamic Style Options

Before touching the canvas, run the **four-question brief** (maximum five
minutes):

| Question | Output | Written to `DESIGN.md` |
|---|---|---|
| What kind of app? | product class (operational, content, multi-module, utility) | `style_direction` |
| Who is the user? | who, usage context, familiarity | `style_notes`, `copy_tone` |
| What is the main problem? | one friction that must disappear | "Direction and rationale" section |
| What is the outcome? | one measurable result for the user | "Direction and rationale" section |

Then **offer 2–3 UI style/layout directions** suited to the context — the user
chooses or steers. Never force a single uniform style.

| Direction | Best for | Character |
|---|---|---|
| `dense operational` | professional workflows, dense data | tight rows, three columns, fast actions |
| `bento / modular` | multi-module dashboards, summaries | asymmetric card grid, clear scale |
| `editorial` | content, documentation, reading | type rhythm, measured line length |
| `clean utility` | narrow tools, setup, forms | single focus, minimal decoration |

Token levers for each direction: `style-directions.md`. `custom` is allowed when
`style_notes` explains the reason.

Reject AI slop firmly: empty decoration, uniform gradients, and clichéd layouts
that are identical for every domain. Favour **cognitive clarity** — every element
has a reason to exist, and a style decision can be explained in one sentence.

---

## 2. Full Product-Design Competence (Zero Hollow Screens)

Design a system, not merely a screen. Minimum checklist before building:

- **UX Flow & IA:** primary and secondary action flows are clear; information
   hierarchy reads for humans and assistive tools (node order, semantic names,
   machine-readable labels).
- **Functional microcopy:** quick recipes below. Never rely on colour alone —
   include text or an icon.
- **States and edge cases (zero hollow screens):** `empty`, `loading/skeleton`,
   `error`, `disabled/focus`, plus text/data length variants (0 / 1 / many /
   very long). Every state has a real design and is listed in `states` in
   `DESIGN.md`.
- **Modern AI and interaction patterns (when relevant):** proportional status,
   user controls, and transparency without overclaiming (ladder below).
- **Accessibility and handoff-friendly:** AA contrast (AAA when requested),
   visible focus, touch targets ≥ `a11y.minTouchTargetPx`, reduced motion, and a
   composition realistically buildable from the available tokens and builders.

### Microcopy recipes

| Context | Pattern | Example (`en-US`; substitute your `locale`) |
|---|---|---|
| Button | action + object | `Save changes`, not `OK` |
| Helper/format | state the expected format | `PNG or JPG, up to 5 MB` |
| Error/validation | cause + way out | `Could not save: connection lost. Try again.` |
| Empty state | offer an action | `No projects yet. Create your first project.` |
| Toast | transient result, no overclaim | `Changes saved.` |
| Exit path | ghost, no accent | `Cancel`, `Close`, `Discard` |

Language follows `locale` + `copy_tone` in `DESIGN.md`, not the skill's language.

### Zero-state matrix (minimum)

| State | What must be designed |
|---|---|
| `default` | normal view; clear three-sweep hierarchy |
| `hover` | temporary feedback via the `hover` token; gone when the pointer leaves |
| `focus` | `ring` 2px, offset 2px; always visible |
| `disabled` | `opacity: 0.45`; action blocked immediately, never a new colour |
| `empty` | heading + description + action (no illustration) |
| `loading` | ≤1s disable controls; >1s spinner; >3s staged progress labels |
| `error` | cause + solution; inline and persistent when it must be read/retried |
| `success` | concise confirmation; avoid claims without real data |

Include length variants too: very long text, 0/1/many rows, and extreme data.
That is what separates a living screen from a UI skin.

### AI/progress status ladder

| Duration | Display |
|---|---|
| 0–100 ms | no indicator (too fast to throttle) |
| 100 ms–1 s | disable the affected control |
| 1–3 s | disable + spinner |
| 3 s+ / multi-stage | staged progress label + cancel/retry control |

- Reserve room for swapping labels with `width`, not `min-width`.
- Always give the user a way out: `Cancel`, `Retry`, or `Edit`.
- Keep internal process private, but show results and limits honestly.

### Accessibility (binds every direction)

- Text/layer contrast at least **AA** (4.5:1 normal, 3:1 large); when
  `a11y.minContrast = "AAA"`, target 7:1 / 4.5:1.
- Keyboard focus always visible; `prefers-reduced-motion` respected per element
  (spinners may remain alive).
- Touch targets ≥ `a11y.minTouchTargetPx` in touch contexts.
- Status never colour-only — pair it with text or an icon.
- FigCraft node order follows a sensible reading order; names are semantic.
- Handoff includes tokens, builders, states, and contrast notes — not just a PNG.

---

## 3. Component-First and Reuse (Duplicate → Refine)

1. **Build base components first:** `input`, `form`, `button`, `icon`,
   `card`/`list item`, and repeated elements — each with clear *variants* and
   *properties* (`size`, `tone`, `state`).
2. **Token hierarchy:** `primitive → semantic → component` (then `theme/state`).
   Components never use raw hex; they use semantic tokens. Details:
   `token-architecture.md`.
3. **In FigCraft, `Duplicate → Refine` is mandatory:** if a component already
   exists, copy it — never rebuild it. Call `ensure_board()` and
   `find_or_reuse_component()` from `figcraft_tool.py` first; when a board or
   component is present, reuse it and adjust only the needed properties, text,
   or coordinates. `duplicate_node()` deep-clones the subtree with fresh unique
   IDs, so repeated items never collide. Do not assemble raw nodes from scratch
   for every screen — that is a source of inconsistency and slow iteration.
4. **The three-board container:** `00_Foundations` (tokens from `DESIGN.md`),
   `01_Components` (bases and variants), and `02_Screens` (screens built by
   duplicating nodes from `01_Components`) are adjacent top-level frames on any
   page in `pages[0..N]`; the default `pages[0]` is simply what the live canvas
   shows first. `quick_design.py --preset three-board` implements this standard
   with `page_index` / `page_name` selectors, and smart reuse can copy
   components across pages.
5. Changes to a parent component propagate to descendants. Node names stay
   semantic (`Btn_<Action>`, `Card_<Name>`); match by `name`, not ID.
6. Component states follow `states` in `DESIGN.md`; do not add ad hoc states that
   are not recorded.
7. When duplicating, preserve parent fill/stroke/radius/padding first, then
   refine. A duplicate that loses its styling is a visual regression defect.

---

## 4. Sharp Execution and Anti-Overthinking

> **Mandatory motto:** *"Not code that is clever and impressive, but code that is
> targeted, correct, and fits the actual need and root cause."* Being impressive
> without hitting the target is slop. If a real trial shows a lacking result,
> keep fixing it together with `Kuron Developer` until it is correct and
> on-target.

- Design decisions are **measurable, decisive, and directly on the need** — no
  drawn-out aesthetic debate.
- Time-box: brief ≤5 min → pick one direction → write `DESIGN.md` → components
  first → build → verify 3–5x.
- Guardrails remain absolute: zero private paths, zero secrets, green tests, and
  the 3–5x PNG loop. Sharpness is not a licence to skip evidence.
- Anti-Overthinking means cutting discussion that would not change a decision,
  not cutting visual verification.

---

## One-Line Summary

`domain brief → offer directions → choose & write DESIGN.md → components first →
Duplicate & refine → complete states → accessible → decisive execution → PNG
proof`.
