#!/usr/bin/env python3
"""Design-manifest loader, validator, resolver, and builder-token adapter.

This module is the single bridge between a project's ``DESIGN.md``
(``design-contract/v1``) and the FigCraft builders. It uses only the Python
standard library. A missing or invalid manifest is always an actionable error:
there is deliberately no silent fallback to an in-code preset.
"""

import copy
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

START_MARKER = "<!-- design-contract:v1:start -->"
END_MARKER = "<!-- design-contract:v1:end -->"
SCHEMA_PREFIX = "kuron-design-figcraft/design-contract/"
SCHEMA_V1 = SCHEMA_PREFIX + "v1"
ENV_OVERRIDE = "FIGCRAFT_DESIGN_MANIFEST"
MANIFEST_NAME = "DESIGN.md"

# Hard limits: no resolver or search loop is allowed to run without a bound.
MAX_REF_DEPTH = 64
MAX_SEARCH_DEPTH = 64
MAX_DESCRIPTIONS = 200

THEMES = ("dark", "light")
STYLE_DIRECTIONS = frozenset({
    "dense_operational", "bento_modular", "editorial", "clean_utility", "custom",
})
REQUIRED_KEYS = (
    "name", "version", "style_direction", "default_theme", "locale", "copy_tone",
    "tokens", "a11y", "states",
)
REQUIRED_TOKEN_GROUPS = ("primitive", "semantic", "component")
REQUIRED_SCALES = ("space", "radius", "type", "motion")
REQUIRED_COLOR_ROLES = (
    "bg", "surface", "surface-2", "raised", "hover", "selected", "line",
    "line-strong", "ring", "text", "text-2", "text-3", "action-primary",
    "action-primary-hover", "action-primary-fg", "action-primary-soft",
    "data-technical", "data-technical-soft", "status-success",
    "status-success-soft", "status-warn", "status-warn-soft", "status-danger",
    "status-danger-soft", "status-info", "status-info-soft",
)

# Legacy builder aliases -> canonical semantic roles. The aliases are kept so
# existing builders keep working while their values come from DESIGN.md.
ROLE_ALIASES = {
    "bg_app": "bg",
    "surface": "surface",
    "surface_2": "surface-2",
    "surface_card": "raised",
    "surface_active": "hover",
    "border": "line",
    "border_subtle": "line",
    "border_accent": "line-strong",
    "ink_primary": "text",
    "ink_secondary": "text-2",
    "ink_muted": "text-3",
    "coral": "action-primary",
    "coral_hover": "action-primary-hover",
    "coral_fg": "action-primary-fg",
    "coral_subtle": "action-primary-soft",
    "cyan": "data-technical",
    "cyan_subtle": "data-technical-soft",
    "success": "status-success",
    "success_subtle": "status-success-soft",
    "warning": "status-warn",
    "warning_subtle": "status-warn-soft",
    "danger": "status-danger",
    "danger_subtle": "status-danger-soft",
    "info": "status-info",
    "info_subtle": "status-info-soft",
    "ring": "ring",
    "selected": "selected",
    "glass_bg": "glass-bg",
    "glass_toolbar": "glass-toolbar",
    "glass_floating": "glass-floating",
    "glass_specular": "glass-specular",
    "glass_border": "glass-border",
    "glass_shadow": "glass-shadow",
}

# Cache keyed by (absolute path, mtime_ns) so repeated builder calls do not
# re-read and re-parse the same manifest on every hot-path operation.
_MANIFEST_CACHE: Dict[Tuple[str, int], Dict[str, Any]] = {}


class DesignManifestError(ValueError):
    """An actionable DESIGN.md discovery, parsing, or validation failure."""


def clear_cache() -> None:
    """Drop cached manifests (used by tests and after an in-place edit)."""
    _MANIFEST_CACHE.clear()


def _package_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _search_dirs(start: Optional[str] = None):
    """Yield cwd upward to the repo/package boundary, then the package root."""
    current = os.path.abspath(start or os.getcwd())
    visited = set()
    for _ in range(MAX_SEARCH_DEPTH):
        if current in visited:
            break
        visited.add(current)
        yield current
        boundary = (
            os.path.isdir(os.path.join(current, ".git"))
            or os.path.isfile(os.path.join(current, "pyproject.toml"))
            or os.path.isfile(os.path.join(current, "SKILL.md"))
        )
        if boundary:
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    # The skill package ships its own explicit DESIGN.md. This is a real file,
    # not an in-code preset, so using it for the package's own tooling is
    # consistent with the "no silent fallback" rule.
    root = _package_root()
    if root not in visited:
        yield root


def find_design(path: Optional[str] = None) -> str:
    """Locate DESIGN.md and return its absolute path, or fail with guidance."""
    override = path or os.environ.get(ENV_OVERRIDE)
    if override:
        candidate = os.path.abspath(os.path.expanduser(override))
        if os.path.isdir(candidate):
            candidate = os.path.join(candidate, MANIFEST_NAME)
        if not os.path.isfile(candidate):
            raise DesignManifestError(
                "DESIGN.md not found at the configured path: %s. "
                "Set %s to a valid file, or copy references/%s from the skill "
                "package into your project root." % (candidate, ENV_OVERRIDE, MANIFEST_NAME)
            )
        return candidate

    searched = []
    for directory in _search_dirs():
        candidate = os.path.join(directory, MANIFEST_NAME)
        searched.append(candidate)
        if os.path.isfile(candidate):
            return candidate
    raise DesignManifestError(
        "No %s found. Searched (in order): %s. Copy references/%s from the "
        "skill package to your project root and fill in the design-contract/v1 "
        "block, or set %s to an explicit path. Silent preset fallback is "
        "forbidden." % (MANIFEST_NAME, ", ".join(searched), MANIFEST_NAME, ENV_OVERRIDE)
    )


def _extract_block(text: str, path: str) -> str:
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start < 0 or end < 0 or end <= start:
        raise DesignManifestError(
            "%s is missing the design-contract/v1 sentinels. Wrap the JSON "
            "block with %s and %s exactly as in references/DESIGN.md."
            % (path, START_MARKER, END_MARKER)
        )
    block = text[start + len(START_MARKER):end].strip()
    # A markdown fence is allowed around the JSON block in the template.
    if block.startswith("```"):
        block = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", block, count=1)
        block = re.sub(r"\s*```$", "", block, count=1).strip()
    return block


def _is_theme_pair(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "dark" in value
        and "light" in value
        and all(isinstance(value[t], (str, int, float)) for t in THEMES)
    )


def resolve(value: Any, doc: Dict[str, Any], theme: Optional[str] = None) -> Any:
    """Resolve ``$...`` references recursively with cycle detection.

    A first segment of ``primitive``/``semantic``/``component`` reads from
    ``tokens``; any other first segment reads from the document root. An
    optional ``tokens.`` prefix is accepted. Theme pairs collapse to the
    requested theme; omitting ``theme`` keeps the pair intact.
    """
    return _resolve(value, doc, theme, ())


def _resolve(value: Any, doc: Dict[str, Any], theme: Optional[str],
             seen: Tuple[str, ...]) -> Any:
    if _is_theme_pair(value):
        if theme is None:
            return {key: _resolve(item, doc, None, seen) for key, item in value.items()}
        if theme not in THEMES:
            raise DesignManifestError(
                "Unknown theme %r; expected one of %s." % (theme, ", ".join(THEMES))
            )
        return _resolve(value[theme], doc, theme, seen)

    if isinstance(value, str):
        if not value.startswith("$"):
            return value
        raw = value[1:].strip()
        if raw.startswith("tokens."):
            raw = raw[len("tokens."):]
        parts = [part for part in raw.split(".") if part]
        if not parts:
            raise DesignManifestError("Empty token reference %r." % value)
        if len(seen) >= MAX_REF_DEPTH or raw in seen:
            chain = " -> ".join(seen + (raw,))
            raise DesignManifestError(
                "Token reference cycle or excessive depth detected: %s "
                "(limit %d)." % (chain, MAX_REF_DEPTH)
            )
        root = doc.get("tokens", {}) if parts[0] in REQUIRED_TOKEN_GROUPS else doc
        current: Any = root
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                raise DesignManifestError(
                    "Unresolved token reference %r: key %r is missing."
                    % (value, part)
                )
            current = current[part]
        return _resolve(current, doc, theme, seen + (raw,))

    if isinstance(value, dict):
        return {key: _resolve(item, doc, theme, seen) for key, item in value.items()}

    if isinstance(value, list):
        return [_resolve(item, doc, theme, seen) for item in value]

    return value


def _rgb(value: Any) -> Optional[Tuple[float, float, float]]:
    """Parse a hex or rgb()/rgba() colour into 0..1 channels."""
    text = str(value).strip()
    if text.startswith("#"):
        digits = text[1:]
        if len(digits) == 3:
            digits = "".join(char * 2 for char in digits)
        if len(digits) == 8:
            digits = digits[:6]
        if len(digits) != 6:
            return None
        try:
            return tuple(int(digits[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        except ValueError:
            return None
    match = re.match(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)", text)
    if match:
        return tuple(float(part) / 255.0 for part in match.groups())
    return None


def contrast_ratio(foreground: Any, background: Any) -> Optional[float]:
    """Return the WCAG contrast ratio, or None for a non-colour value."""
    a, b = _rgb(foreground), _rgb(background)
    if a is None or b is None:
        return None

    def luminance(channels: Tuple[float, float, float]) -> float:
        def linear(channel: float) -> float:
            return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
        r, g, blue = channels
        return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(blue)

    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _fail(message: str) -> None:
    raise DesignManifestError(message)


def validate(doc: Any) -> Dict[str, Any]:
    """Validate a parsed manifest and return it unchanged.

    Every failure raises ``DesignManifestError`` with the exact field and a
    concrete fix, so an agent never has to guess why the contract is rejected.
    """
    if not isinstance(doc, dict):
        _fail("DESIGN.md contract must be a JSON object.")

    schema = doc.get("$schema")
    if not isinstance(schema, str) or not schema.startswith(SCHEMA_PREFIX):
        _fail("$schema must start with %r (found %r)." % (SCHEMA_PREFIX, schema))

    for key in REQUIRED_KEYS:
        if key not in doc:
            _fail("Missing required key %r in the design-contract/v1 block." % key)
    for key in ("name", "version", "style_direction", "default_theme", "locale", "copy_tone"):
        if not isinstance(doc[key], str) or not doc[key].strip():
            _fail("Required string %r must be non-empty." % key)
    if doc["style_direction"] not in STYLE_DIRECTIONS:
        _fail("style_direction %r is not one of %s."
              % (doc["style_direction"], ", ".join(sorted(STYLE_DIRECTIONS))))
    if doc["default_theme"] not in THEMES:
        _fail("default_theme %r must be 'dark' or 'light'." % doc["default_theme"])

    tokens = doc["tokens"]
    if not isinstance(tokens, dict):
        _fail("tokens must be an object.")
    for group in REQUIRED_TOKEN_GROUPS:
        if not isinstance(tokens.get(group), dict) or not tokens[group]:
            _fail("tokens.%s must be a non-empty object." % group)

    primitive = tokens["primitive"]
    semantic = tokens["semantic"]
    component = tokens["component"]
    colors = primitive.get("color")
    if not isinstance(colors, dict) or not colors:
        _fail("tokens.primitive.color must be a non-empty object of themed colours.")
    for name, value in colors.items():
        if not _is_theme_pair(value):
            _fail("tokens.primitive.color.%s must have both 'dark' and 'light' values." % name)
        for theme in THEMES:
            if not isinstance(value[theme], str) or not value[theme].strip():
                _fail("tokens.primitive.color.%s.%s must be a non-empty string." % (name, theme))
    for scale in REQUIRED_SCALES:
        group = primitive.get(scale)
        if not isinstance(group, dict) or not group:
            _fail("tokens.primitive.%s must be a non-empty numeric scale." % scale)
        for key, value in group.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                _fail("tokens.primitive.%s.%s must be a number." % (scale, key))

    semantic_colors = semantic.get("color")
    if not isinstance(semantic_colors, dict):
        _fail("tokens.semantic.color must be an object.")
    for role in REQUIRED_COLOR_ROLES:
        if role not in semantic_colors:
            _fail("Missing semantic colour role %r in tokens.semantic.color." % role)
        value = semantic_colors[role]
        if _is_theme_pair(value):
            for theme in THEMES:
                if not value[theme]:
                    _fail("Semantic role %r has an empty %s value." % (role, theme))
        elif not (isinstance(value, str) and value.strip()):
            _fail("Semantic role %r must be a reference, a themed pair, or a literal." % role)
    for scale in REQUIRED_SCALES:
        group = semantic.get(scale)
        if not isinstance(group, dict) or not group:
            _fail("tokens.semantic.%s must be a non-empty object of role references." % scale)

    if not component:
        _fail("tokens.component must contain component sizes.")
    for name, value in component.items():
        if not isinstance(value, dict):
            _fail("tokens.component.%s must be an object." % name)

    a11y = doc["a11y"]
    if not isinstance(a11y, dict):
        _fail("a11y must be an object.")
    level = str(a11y.get("minContrast", "")).upper()
    if level not in ("AA", "AAA"):
        _fail("a11y.minContrast must be 'AA' or 'AAA'.")
    ratios = a11y.get("minContrastRatio")
    if not isinstance(ratios, dict):
        _fail("a11y.minContrastRatio must be an object with normal/large thresholds.")
    key = "aaaNormal" if level == "AAA" else "normal"
    if key not in ratios or not isinstance(ratios[key], (int, float)):
        _fail("a11y.minContrastRatio.%s must be a number for %s." % (key, level))
    required = float(ratios[key])
    if not isinstance(a11y.get("minTouchTargetPx"), (int, float)):
        _fail("a11y.minTouchTargetPx must be a number.")

    states = doc["states"]
    if not isinstance(states, list) or not states:
        _fail("states must be a non-empty array of state names.")
    for state in states:
        if not isinstance(state, str) or not state.strip():
            _fail("Every entry in states must be a non-empty string.")

    # Resolve every reference in both themes. This catches cycles, dangling
    # references, and missing theme pairs before any builder consumes them.
    pairs = []
    for theme in THEMES:
        try:
            pairs.append(resolve(semantic_colors, doc, theme))
        except DesignManifestError as exc:
            _fail("%s theme: %s" % (theme, exc))
        try:
            resolve(component, doc, theme)
        except DesignManifestError as exc:
            _fail("component (%s theme): %s" % (theme, exc))
    for scale in REQUIRED_SCALES:
        try:
            resolve(semantic[scale], doc, THEMES[0])
        except DesignManifestError as exc:
            _fail("tokens.semantic.%s: %s" % (scale, exc))

    # Contrast thresholds apply to both themes, not only the default one.
    for theme, resolved in zip(THEMES, pairs):
        checks = (
            ("text", "bg"),
            ("action-primary", "action-primary-fg"),
            ("data-technical", "bg"),
        )
        for foreground, background in checks:
            ratio = contrast_ratio(resolved[foreground], resolved[background])
            if ratio is None:
                _fail("%s theme: cannot measure contrast of %s on %s."
                      % (theme, foreground, background))
            if ratio + 1e-9 < required:
                _fail(
                    "%s theme: contrast of %s on %s is %.2f:1, below the %s "
                    "threshold %.2f:1. Adjust the paired tokens in DESIGN.md."
                    % (theme, foreground, background, ratio, level, required)
                )
    return doc


def load_design(path: Optional[str] = None) -> Dict[str, Any]:
    """Find, parse, validate, and cache the project design manifest."""
    manifest_path = find_design(path)
    try:
        stat = os.stat(manifest_path)
    except OSError as exc:
        raise DesignManifestError("Cannot read %s: %s" % (manifest_path, exc)) from exc
    cache_key = (manifest_path, stat.st_mtime_ns)
    cached = _MANIFEST_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise DesignManifestError("Cannot read %s: %s" % (manifest_path, exc)) from exc
    block = _extract_block(text, manifest_path)
    try:
        doc = json.loads(block)
    except json.JSONDecodeError as exc:
        raise DesignManifestError(
            "Invalid JSON in %s at line %d column %d: %s. Fix the design-contract/v1 "
            "block and keep the two sentinel comments."
            % (manifest_path, exc.lineno, exc.colno, exc.msg)
        ) from exc
    validate(doc)
    _MANIFEST_CACHE[cache_key] = doc
    return copy.deepcopy(doc)


def to_builder_tokens(doc: Dict[str, Any], theme: Optional[str] = None) -> Dict[str, Any]:
    """Convert a validated manifest into the legacy builder token structure.

    ``TOKENS['colors']`` keeps every historical alias (``coral``, ``cyan``,
    ``bg_app``, ...) but its value now comes from the resolved semantic role in
    DESIGN.md. Canonical roles are exposed under the same key as well.
    """
    validate(doc)
    chosen = theme or doc["default_theme"]
    if chosen not in THEMES:
        _fail("Unknown theme %r; expected 'dark' or 'light'." % chosen)

    tokens = resolve(doc["tokens"], doc, chosen)
    primitive = tokens["primitive"]
    semantic = tokens["semantic"]
    sem_color = semantic["color"]

    colors: Dict[str, Any] = {}
    for alias, role in ROLE_ALIASES.items():
        if role in sem_color:
            colors[alias] = sem_color[role]
    for role, value in sem_color.items():
        colors[role] = value  # canonical role names take priority

    fonts = doc.get("fonts") if isinstance(doc.get("fonts"), dict) else {}
    sizes = tokens["component"]
    ui_font = fonts.get("ui", "Inter")
    brand_font = fonts.get("brand", "Space Grotesk")
    mono_font = fonts.get("mono", "JetBrains Mono")
    typography = {
        "font_ui": ui_font,
        "font_brand": brand_font,
        "font_mono": mono_font,
        "sizes": {
            "hero": primitive["type"].get("hero", semantic["type"]["display"]),
            "title": semantic["type"]["display"],
            "heading": semantic["type"]["heading"],
            "body": semantic["type"]["body"],
            "caption": semantic["type"]["caption"],
            "badge": semantic["type"]["mono"],
        },
    }
    radii = {
        "control": semantic["radius"]["control"],
        "badge": semantic["radius"]["pill"],
        "card": semantic["radius"]["card"],
        "window": semantic["radius"]["window"],
    }
    button = sizes.get("button", {}).get("height", {})
    icon = sizes.get("icon", {})
    header = sizes.get("header", {})
    builder_sizes = {
        "btn_sm": button.get("sm", semantic["type"]["caption"]),
        "btn_md": button.get("md", semantic["type"]["control"] + 4),
        "btn_lg": button.get("lg", semantic["type"]["body"] + 8),
        "field": sizes.get("field", {}).get("height", semantic["type"]["body"] + 8),
        "icon_sm": icon.get("sm", semantic["type"]["mono"] + 6),
        "icon_md": icon.get("md", semantic["type"]["mono"] + 10),
        "icon_lg": icon.get("lg", semantic["type"]["control"] + 12),
        "header": header.get("height", button.get("md", semantic["type"]["control"])),
        "window_bar": header.get("height", button.get("md", semantic["type"]["control"])),
    }
    return {
        "colors": colors,
        "typography": typography,
        "radii": radii,
        "sizes": builder_sizes,
        "style_direction": doc["style_direction"],
        "locale": doc["locale"],
        "copy_tone": doc["copy_tone"],
        "theme": chosen,
        "name": doc["name"],
        "a11y": resolve(doc["a11y"], doc, chosen),
        "screens": doc.get("screens", []),
        "content": doc.get("content", {}),
        "fonts": fonts,
    }


def _preset_doc() -> Optional[Dict[str, Any]]:
    """Read the package's own manifest for override comparison."""
    path = os.path.join(_package_root(), MANIFEST_NAME)
    if not os.path.isfile(path):
        return None
    try:
        return load_design(path)
    except DesignManifestError:
        return None


def describe_overrides(doc: Dict[str, Any]) -> List[str]:
    """Describe differences between ``doc`` and the bundled preset.

    The result is a bounded list of short ``field: preset -> project`` lines
    suitable for an audit report. If no baseline is available, a compact
    contract summary is returned instead.
    """
    validate(doc)
    preset = _preset_doc()
    if preset is None:
        return [
            "style_direction=%s" % doc["style_direction"],
            "default_theme=%s" % doc["default_theme"],
            "locale=%s" % doc["locale"],
        ]

    descriptions: List[str] = []
    baseline = to_builder_tokens(preset, preset["default_theme"])["colors"]
    current = to_builder_tokens(doc, doc["default_theme"])["colors"]
    for key in sorted(set(baseline) | set(current)):
        if len(descriptions) >= MAX_DESCRIPTIONS:
            break
        if baseline.get(key) != current.get(key):
            descriptions.append("%s: %s -> %s" % (key, baseline.get(key), current.get(key)))
    for field in ("style_direction", "default_theme", "locale", "copy_tone"):
        if len(descriptions) >= MAX_DESCRIPTIONS:
            break
        if doc[field] != preset[field]:
            descriptions.append("%s: %s -> %s" % (field, preset[field], doc[field]))
    return descriptions


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inspect a design-contract/v1 manifest.")
    parser.add_argument("--path", help="Explicit DESIGN.md path")
    parser.add_argument("--theme", choices=THEMES, help="Resolve tokens for this theme")
    parser.add_argument("--overrides", action="store_true", help="List preset overrides")
    args = parser.parse_args()
    document = load_design(args.path)
    if args.overrides:
        for line in describe_overrides(document):
            print(line)
    elif args.theme:
        print(json.dumps(to_builder_tokens(document, args.theme), indent=2, default=str))
    else:
        print(json.dumps({"name": document["name"], "style_direction": document["style_direction"],
                          "default_theme": document["default_theme"]}, indent=2))
