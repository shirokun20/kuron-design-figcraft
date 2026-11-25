# Live Workflow — Editing, Generation, Feedback, Audit and Export

The official workflow for **live editing/generating** `.figcraft` files through
`scripts/agent_terminal.py` (TCP control port, default `9880`). Use this module
when editing, generating, monitoring, exporting, or verifying screens live.
Every colour/size used during a session **MUST** come from the project's
`DESIGN.md` (`design-tokens.css` is only a preset). Pair with
`dark-artifact-rules.md` (execution) and `light-glass-system.md` (theme/surface)
for aesthetic rules, and `style-directions.md` for direction.

Run all commands from the package root.

---

## 1. Global Flag and Path Rules

- The global flag **`--port <PORT>` MUST appear BEFORE the subcommand**:

  ```bash
  python3 scripts/agent_terminal.py --port 9880 status
  ```

- The port is freely changeable (`--port 9901`, etc.) when the default is busy.
  It is not a constant — always read it from the flag or `.figcraft.port`.
- `.figcraft` paths are **cwd-tolerant**: relative paths resolve against the
  working directory/root containing the file. The default can be overridden via
  env `FIGCRAFT_DESIGN`.
- PID/port files (`.figcraft.pid`, `.figcraft.port`) are written in the current
  working directory.
- The FigCraft binary location can be overridden via env `FIGCRAFT_APP`.

---

## 1.1 Mandatory Live Capabilities (not optional)

| Capability | Scope | Minimum flow | Pass evidence |
|---|---|---|---|
| **Live Editing** | change nodes, properties, and **tokens** live; sync to file | `exec node.set` / `select.set` / `file.save` → `reload --soft` → `diff --id` | Property changed + fresh PNG |
| **Live Generate** | **Components**, **Screen**, **Form**, modal/drawer, list/table, badges, empty/error states | call builders from `figcraft_tool.py` in-session → `frames` for real IDs → `export` | New nodes in `frames` and correct in PNG |
| **Live Feedback** | session status, frame list, property diff, change watch | `status` → `frames` → `diff --id <ID>` → `watch` | IDs read, never guessed |
| **Live Audit** | utilisation, overflow, topology, semantics, contrast | `audit_render.py` + pixel-by-pixel PNG inspection | Green audit numbers + clean PNG |
| **Live Export** | single frame / all frames with scale | `export --id`, `export-all -o <dir> --scale N` | PNG opened, not merely listed |
| **Other flows** | open another file, reload, REPL, manifest, stop, parallel work | `open`, `reload --soft/--hard`, `interactive`, `harness-info`, `stop`, `multi_agent_worker.py` | Session stopped cleanly, lock released |

**Hard rules for Live Generate:**

1. Generate using **builders + `DESIGN.md` tokens**, not frozen script values.
2. New components follow **Duplicate → Refine**: copy the parent component, then
   change only what is needed — do not assemble raw nodes per screen.
3. After generating, always `frames` first for real IDs, then `diff`, then
   `export`, then open the PNG. **JSON is not visual evidence.**
4. Generated states (`empty/loading/error/disabled/focus/success`) must be
   complete per `states` in `DESIGN.md`.
5. Forms/modals/drawers/tables must use consistent Auto-Layout and `clip: true`
   on screen-level frames (see §5.1).

---

## 2. Subcommand List

| Subcommand | Use | Example |
|---|---|---|
| `start` | Launch FigCraft with a live port (`--file/-f`, `--no-wait`) | `--port 9880 start --file out/workbench.figcraft` |
| `status` | Check socket health and active document | `--port 9880 status` |
| `open` | Open another file in the running instance | `--port 9880 open out/other.figcraft` |
| `frames` | List screen-level frames (`id`, `name`, `x/y/w/h`); `--json` | `--port 9880 frames` |
| `reload` | `--soft` (default, safe) or `--hard` (forced); uses the active file when no path is given | `--port 9880 reload --soft` |
| `watch` | Watch mtime → auto reload + export-all; uses the active file when no path is given | `--port 9880 watch out/workbench.figcraft -o out/previews/ --scale 2 --max-events 200 --max-seconds 600` |
| `exec` | Direct JSON-RPC engine command | `--port 9880 exec select.set '{"ids": [10]}'` |
| `diff` | Summarise one node's properties | `--port 9880 diff --id <ID>` |
| `export` | Export ONE frame (`--id`, `-o`, `--format`, `--scale`) | `--port 9880 export --id <ID> -o out/previews/01.png --scale 2` |
| `export-all` | Export ALL frames to a folder | `--port 9880 export-all -o out/previews/ --scale 2` |
| `interactive` | Interactive REPL (max 10,000 lines) | `--port 9880 interactive` |
| `harness-info` | JSON manifest of harness capabilities | `--port 9880 harness-info` |
| `stop` | Stop the FigCraft process | `--port 9880 stop` |

`start` and `open` persist the active `.figcraft` path; `reload` and `watch`
use it when no path is supplied and fail explicitly if none is known. A failed
reload exits non-zero and `watch` stops without exporting a stale document.

Example manifest:

```bash
python3 scripts/agent_terminal.py --port 9880 harness-info
# => {"name": "kuron-design-figcraft", "version": "3.2.0", ...}
```

---

## 3. Mandatory Live Visual Feedback Loop

Never edit `.figcraft` blindly or treat a build as successful from its exit code.
Run this closed cycle:

1. **Start and discover**
   - `start --file <file>.figcraft`
   - `frames` to obtain real frame IDs — **never guess IDs**.
2. **Edit / mutate / generate**
   - Change via Python builders (`figcraft_tool.py`) or mutation through `exec`
     (`node.set`, `select.set`, `file.save`).
   - Builders must read roles from `DESIGN.md`; reload values if the document
     changes mid-session.
   - `lint_design()` must report **0 warnings** before export.
3. **Sync to canvas**
   - Fast iteration: `watch <file> -o out/previews/ --scale 2` in a separate
     terminal, or `reload --soft` after each file change.
   - `reload --hard` only when `--soft` does not refresh page/font structure.
4. **Verify mutation and export**
   - `diff --id <ID>` confirms properties actually changed.
   - `export --id <ID>` or `export-all` produces visual evidence.
5. **Inspect the PNG pixel by pixel**
   - Open the PNG; check for clipped text, overlaps, clean contrast, and tidy
     `clip: true` corners.
   - Repeat 2–5 until one full pass is clean (minimum 3 for a new screen,
     maximum 5).
6. **Cleanup**
   - `stop` when the session is finished and no other agent uses that port.

---

## 4. Example `exec` Patterns

```bash
# Select a node
python3 scripts/agent_terminal.py --port 9880 exec select.set '{"ids": [<ID>]}'

# Change a property (validate JSON first)
python3 scripts/agent_terminal.py --port 9880 exec node.set '{"id": <ID>, "name": "<name>"}'

# Save the active document
python3 scripts/agent_terminal.py --port 9880 exec file.save '{}'
```

Use single quotes around JSON in the shell so it is not reinterpreted.

---

## 5. Guardrails and Troubleshooting

- **Invalid JSON is rejected** before reaching the socket, with a friendly
  message showing a valid example.
- **Busy port / stale PID:** run `status` first. If the socket is dead but
  `.figcraft.pid` remains, `stop` then `start` again (or change `--port`).
- **Never run two writers** on the same `.figcraft` file; `watch` only reads and
  renders. For parallel work use `multi_agent_worker.py` (ID namespaces + `.figcraft.lock`).
- **Never claim from JSON metadata:** the proof is the PNG that was opened.
- **All sockets have timeouts** (`send_rpc`, `FigcraftClient.connect`, workers),
  and all read/poll loops have cut-loop guards:
  - `send_rpc`: at most 1024 `recv()` chunks per response.
  - `watch`: `--max-events` (default 1000) and `--max-seconds` (default 3600).
  - `interactive`: at most 10,000 lines.
- **Binary missing:** `start` reports a clear error. Set `FIGCRAFT_APP` to the
  binary location; offline operations (builder/lint/save) still work.
- **Stale session:** after headless edits outside the session, `reload --hard`
  or open another file then reopen the target before any visual claim.
- **`DESIGN.md` changed:** treat it as a visual change — reload tokens,
  `reload --soft` (or `--hard` if structure changed), then repeat the 3–5x loop.
  Never claim using stale colours cached in the session.

---

## 5.1 Visual Regression Guard — Six Defects That Must Never Pass

Check these in the **PNG**, not in JSON:

1. **Text outside a border/frame** → fix `width`/`sizing`/Auto-Layout; do not
   simply truncate the text.
2. **Clipped or overlapping text** → one line = one node; reserve room with
   `width` (not `min-width`); editing text always means re-export.
3. **`clip: false` on a screen frame** → set `clip: true`; content must not leak
   past the rounded frame.
4. **Inconsistent Auto-Layout** → padding/gap follow the `semantic.space` ladder;
   `fill/fixed/hug` follow roles; no "almost equal" numbers.
5. **Duplicates lose styling/padding** → `diff --id` parent vs duplicate; copy
   fill/stroke/radius/padding from the parent component before refining.
6. **JSON differs from the real PNG** → trust the PNG: fix structure, `reload`,
   export again, look again.

Exit gate remains: at least 3 full passes, at most 5. If defects remain, **do
not ship** — keep fixing together with `Kuron Developer` until it is correct and
on-target, per the skill motto.

---

## 6. One-Line Summary

`status/start → harness-info → frames → generate/edit → reload/watch → diff →
export/export-all → audit → inspect PNG (3–5x) → stop`.
