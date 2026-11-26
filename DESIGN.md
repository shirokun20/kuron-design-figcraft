# DESIGN.md — FigCraft Reference Preset

> Contract: `design-contract/v1` · Compatible with `kuron-design-figcraft` 3.2.3
>
> This file is the **skill package's own** design manifest. It is the explicit
> source of the bundled preset values consumed by the reference scripts. A
> consuming project must ship **its own** `DESIGN.md`, copied from
> `references/DESIGN.md` and edited for that project. Loading a project without
> a manifest is a hard, actionable error — never a silent fallback.
>
> The `fonts`, `screens`, `content`, and `lint` keys below are optional
> extensions read by the bundled reference generator. They are not part of the
> required `design-contract/v1` schema and may be ignored by consumers.

<!-- design-contract:v1:start -->
```json
{
  "$schema": "kuron-design-figcraft/design-contract/v1",
  "name": "FigCraft Reference Preset",
  "version": "1.0.0",
  "style_direction": "dense_operational",
  "style_notes": "Neutral operational preset for the bundled reference screens.",
  "default_theme": "dark",
  "locale": "en-US",
  "copy_tone": "direct, action + object",

  "tokens": {
    "primitive": {
      "color": {
        "n0": {"dark": "#0d0d10", "light": "#f7f6f4"},
        "n1": {"dark": "#141418", "light": "#ffffff"},
        "n2": {"dark": "#1a1a20", "light": "#f1f0ed"},
        "n3": {"dark": "#22222a", "light": "#e8e7e3"},
        "n4": {"dark": "#2a2a33", "light": "#deddd8"},
        "n5": {"dark": "#34343f", "light": "#d8d7d1"},
        "l0": {"dark": "#26262e", "light": "#dfdfd9"},
        "l1": {"dark": "#35353f", "light": "#c4c3bc"},
        "ring": {"dark": "#9a9aa8", "light": "#55555f"},
        "i0": {"dark": "#ececf1", "light": "#16161a"},
        "i1": {"dark": "#a5a6b0", "light": "#55555f"},
        "i2": {"dark": "#71727d", "light": "#7c7c86"},
        "brand": {"dark": "#ff6b5a", "light": "#c4342a"},
        "brandHover": {"dark": "#ff8272", "light": "#a62a21"},
        "brandFg": {"dark": "#1a0a08", "light": "#ffffff"},
        "brandSoft": {"dark": "#2e1614", "light": "#fbe9e7"},
        "tech": {"dark": "#35e7f5", "light": "#0b6e78"},
        "techSoft": {"dark": "#0e2a2e", "light": "#e0f2f4"},
        "ok": {"dark": "#5fd99a", "light": "#1f7a4d"},
        "okSoft": {"dark": "#10281d", "light": "#e4f3ea"},
        "warn": {"dark": "#ffc15e", "light": "#8a5a00"},
        "warnSoft": {"dark": "#2b2110", "light": "#fbf0dc"},
        "danger": {"dark": "#ff5c5c", "light": "#b3261e"},
        "dangerSoft": {"dark": "#2e1416", "light": "#fde8e6"},
        "info": {"dark": "#6ba6ff", "light": "#1f5fbf"},
        "infoSoft": {"dark": "#111e33", "light": "#e5eefb"},
        "glassBg": {"dark": "rgba(34,34,42,0.72)", "light": "rgba(255,255,255,0.72)"},
        "glassToolbar": {"dark": "rgba(26,26,32,0.78)", "light": "rgba(241,240,237,0.78)"},
        "glassFloating": {"dark": "rgba(42,42,51,0.88)", "light": "rgba(255,255,255,0.88)"},
        "glassSpecular": {"dark": "rgba(255,255,255,0.14)", "light": "rgba(255,255,255,0.70)"},
        "glassBorder": {"dark": "rgba(236,236,241,0.10)", "light": "rgba(22,22,26,0.08)"},
        "glassShadow": {"dark": "0 8px 24px rgba(0,0,0,0.28), 0 1px 2px rgba(0,0,0,0.16)", "light": "0 8px 24px rgba(22,22,26,0.08), 0 1px 2px rgba(22,22,26,0.04)"}
      },
      "space": {"0": 0, "1": 4, "2": 8, "3": 12, "4": 16, "5": 20, "6": 24},
      "radius": {"xs": 6, "sm": 8, "md": 12, "lg": 16, "pill": 9999},
      "type": {"hero": 28, "display": 20, "heading": 15, "body": 13, "control": 12, "caption": 11, "mono": 10},
      "motion": {"instant": 100, "fast": 200, "normal": 320, "slow": 480}
    },
    "semantic": {
      "color": {
        "bg": "$primitive.color.n0",
        "surface": "$primitive.color.n1",
        "surface-2": "$primitive.color.n2",
        "raised": "$primitive.color.n3",
        "hover": "$primitive.color.n4",
        "selected": "$primitive.color.n5",
        "line": "$primitive.color.l0",
        "line-strong": "$primitive.color.l1",
        "ring": "$primitive.color.ring",
        "text": "$primitive.color.i0",
        "text-2": "$primitive.color.i1",
        "text-3": "$primitive.color.i2",
        "action-primary": "$primitive.color.brand",
        "action-primary-hover": "$primitive.color.brandHover",
        "action-primary-fg": "$primitive.color.brandFg",
        "action-primary-soft": "$primitive.color.brandSoft",
        "data-technical": "$primitive.color.tech",
        "data-technical-soft": "$primitive.color.techSoft",
        "status-success": "$primitive.color.ok",
        "status-success-soft": "$primitive.color.okSoft",
        "status-warn": "$primitive.color.warn",
        "status-warn-soft": "$primitive.color.warnSoft",
        "status-danger": "$primitive.color.danger",
        "status-danger-soft": "$primitive.color.dangerSoft",
        "status-info": "$primitive.color.info",
        "status-info-soft": "$primitive.color.infoSoft",
        "glass-bg": "$primitive.color.glassBg",
        "glass-toolbar": "$primitive.color.glassToolbar",
        "glass-floating": "$primitive.color.glassFloating",
        "glass-specular": "$primitive.color.glassSpecular",
        "glass-border": "$primitive.color.glassBorder",
        "glass-shadow": "$primitive.color.glassShadow"
      },
      "space": {
        "xxs": "$primitive.space.1", "xs": "$primitive.space.2",
        "sm": "$primitive.space.3", "md": "$primitive.space.4",
        "lg": "$primitive.space.5", "xl": "$primitive.space.6"
      },
      "radius": {
        "control": "$primitive.radius.xs", "card": "$primitive.radius.md",
        "window": "$primitive.radius.lg", "pill": "$primitive.radius.pill"
      },
      "type": {
        "display": "$primitive.type.display", "heading": "$primitive.type.heading",
        "body": "$primitive.type.body", "control": "$primitive.type.control",
        "caption": "$primitive.type.caption", "mono": "$primitive.type.mono"
      },
      "motion": {
        "instant": "$primitive.motion.instant", "fast": "$primitive.motion.fast",
        "normal": "$primitive.motion.normal", "slow": "$primitive.motion.slow"
      }
    },
    "component": {
      "button": {"height": {"sm": 28, "md": 32, "lg": 40}, "gap": "$semantic.space.xxs", "radius": "$semantic.radius.control", "label": "$semantic.type.control"},
      "field": {"height": 36, "radius": "$semantic.radius.control", "paddingX": "$semantic.space.sm"},
      "badge": {"height": 20, "radius": "$semantic.radius.pill", "fontSize": "$semantic.type.mono"},
      "card": {"radius": "$semantic.radius.card", "padding": "$semantic.space.sm"},
      "dialog": {"radius": "$semantic.radius.card", "maxWidthPx": 560},
      "icon": {"sm": 16, "md": 20, "lg": 24},
      "header": {"height": 32},
      "focus": {"widthPx": 2, "offsetPx": 2},
      "elevation": {"maxLevels": 3}
    }
  },

  "a11y": {
    "minContrast": "AA",
    "minContrastRatio": {"normal": 4.5, "large": 3.0, "aaaNormal": 7.0, "aaaLarge": 4.5},
    "minTouchTargetPx": 44,
    "focusVisible": {"enabled": true, "widthPx": 2, "offsetPx": 2},
    "reducedMotion": true,
    "neverColorOnly": true,
    "screenReaderLabels": true
  },

  "states": ["default", "hover", "focus", "disabled", "empty", "loading", "error", "success"],

  "fonts": {"ui": "Inter", "brand": "Space Grotesk", "mono": "JetBrains Mono"},
  "screens": [
    {"id": "dashboard", "name": "01. Dashboard", "x": 40, "y": 40, "width": 1280, "height": 960},
    {"id": "grid", "name": "02. Page Grid & Pipeline", "x": 1360, "y": 40, "width": 1280, "height": 960},
    {"id": "editor", "name": "03. Translation Workbench", "x": 2680, "y": 40, "width": 1280, "height": 960},
    {"id": "ledger", "name": "04. Bubble Ledger", "x": 4000, "y": 40, "width": 1280, "height": 960},
    {"id": "export", "name": "05. Export Flow & Modal", "x": 5320, "y": 40, "width": 1280, "height": 960},
    {"id": "system", "name": "06. Design System & Palette", "x": 6640, "y": 40, "width": 1280, "height": 1400},
    {"id": "batch", "name": "07. Batch Translate & Quota", "x": 7960, "y": 40, "width": 1280, "height": 960}
  ],
  "content": {
    "paper": "#f8f8fc",
    "paper_alt": "#e8e8f0",
    "paper_2": "#e2e2ec",
    "paper_3": "#dedee8",
    "paper_4": "#e4e4ee",
    "panel": "#181820",
    "panel_1": "#242430",
    "panel_2": "#1F1F2A",
    "panel_3": "#20202C",
    "manga_card": "#121216",
    "ink": "#000000",
    "ink_soft": "#111111",
    "ink_panel": "#111118",
    "ink_art": "#111115",
    "ink_muted_1": "#555566",
    "ink_muted_2": "#666677",
    "ink_muted_3": "#888899",
    "sheet": "#FFFFFF",
    "sheet_panel_1": "#F0F0F5",
    "sheet_panel_2": "#EBEBF2",
    "scrim": "#0a0a0d",
    "scrim_overlay": "#0A0A0DE0",
    "window_outline": "#444455",
    "traffic_close": "#ff5f56",
    "traffic_min": "#ffbd2e",
    "traffic_max": "#27c93f"
  },
  "geometry": {
    "screen": {"width": 1280, "height": 960, "radius": 16},
    "windowBarHeight": 32,
    "headerHeight": 48,
    "dialog": {"width": 480, "height": 300, "header": 56, "body": 120, "footer": 64, "scrimOpacity": 0.6},
    "railWidth": 196,
    "inspectorWidth": 268,
    "connector": {"head": 10, "dash": [6, 4]},
    "mangaPage": {"width": 520, "height": 740},
    "blocks": {
      "screenGap": 20, "contentGap": 20,
      "statCard": {"width": 240, "height": 84},
      "projectCard": {"width": 300, "height": 340, "coverHeight": 180},
      "ledger": {"height": 500, "header": 36, "row": 44},
      "drawer": {"width": 390, "height": 460, "item": 56}
    }
  },
  "copy": {
    "en-US": {
      "app_name": "Design Studio",
      "new_project": "New project",
      "translate_all": "Translate all",
      "detect_bubbles": "Detect bubbles",
      "project_dashboard": "Project dashboard",
      "translation_ledger": "Translation ledger",
      "quick_settings": "Quick settings",
      "open_editor": "Open editor",
      "import_file": "Import file",
      "save_changes": "Save changes",
      "cancel": "Cancel",
      "status_ready": "Ready",
      "status_error": "Error",
      "search": "Search",
      "empty_title": "Nothing here yet",
      "empty_desc": "Import a file to get started.",
      "error_title": "Request failed",
      "error_fix": "Check the connection and try again.",
      "retry": "Try again",
      "submit": "Submit form",
      "field_name": "Name",
      "field_email": "Email",
      "field_notes": "Notes"
    }
  },
  "lint": {
    "forbiddenNeon": "#00e5ff",
    "contentAllow": [
      "#ffffff", "#111111", "#111118", "#444455", "#f8f8fc",
      "#e8e8f0", "#e2e2ec", "#dedee8", "#e4e4ee",
      "#ff5f56", "#ffbd2e", "#27c93f", "#000000", "#0a0a0d",
      "#121216", "#16161a", "#111115", "#f0f0f5", "#ebebf2",
      "#555566", "#666677", "#888899", "#f7f6f4", "#f1f0ed",
      "#e8e7e3", "#deddd8", "#d8d7d1", "#55555f", "#dfdfd9",
      "#c4c3bc", "#7c7c86", "#c4342a", "#a62a21", "#fbe9e7",
      "#0b6e78", "#e0f2f4", "#1f7a4d", "#e4f3ea", "#8a5a00",
      "#fbf0dc", "#b3261e", "#fde8e6", "#f1958e", "#e0827e",
      "#9d555b", "#1a1a1f", "#1c1816", "#221e1c", "#2a2522",
      "#2e2926", "#4a3d36", "#d4ccc4", "#9e948c", "#efe6dc",
      "#f5ede4", "#fcf7f0", "#faf3ec", "#d6c8bc", "#2e2722",
      "#7a6e66", "#c76a62", "#d48a6a", "#c8a06a"
    ],
    "borderContentAllow": ["#111115", "#22222a", "#4a3d36", "#d6c8bc"],
    "borderAllowedRoles": ["line", "line-strong", "ring", "action-primary"]
  }
}
```
<!-- design-contract:v1:end -->
