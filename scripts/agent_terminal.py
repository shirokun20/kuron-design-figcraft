#!/usr/bin/env python3
"""
FigCraft Agent Terminal & Live Port Controller (kuron-design-figcraft 3.0.0)
Cross-Agent / Harness-Compatible Bridge (Claude Code, Codex, Cursor, generic harnesses)

Provides a dedicated process manager, live JSON-RPC socket bridge, and CLI terminal
to control FigCraft for live UI design inspection, mutation, and automated visual rendering.

All network operations use timeouts and every polling/read loop has a hard cut-loop
guard, so a stalled or chatty control server can never hang an agent forever.
"""

import sys
import os
import re
import json
import time
import socket
import argparse
import subprocess
import signal
from typing import Optional, Dict, Any, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from design_manifest import load_design  # noqa: E402

DEFAULT_PORT = 9880
PID_FILE = os.path.join(os.getcwd(), ".figcraft.pid")
PORT_FILE = os.path.join(os.getcwd(), ".figcraft.port")
# Platform default only; override with FIGCRAFT_APP for other install locations.
DEFAULT_APP_PATH = os.environ.get(
    "FIGCRAFT_APP", "/Applications/FigCraft.app/Contents/MacOS/FigCraft")
DEFAULT_DESIGN_REL = os.environ.get("FIGCRAFT_DESIGN", "design/workbench.figcraft")
HARNESS_VERSION = "3.1.0"
HARNESS_NAME = "kuron-design-figcraft"

# Cut-loop guards: no read/poll loop may run unbounded.
MAX_SOCKET_CHUNKS = 1024          # max recv() calls per JSON-RPC response
MAX_WATCH_EVENTS = 1000           # max file-change events per watch session
MAX_WATCH_SECONDS = 3600.0        # max wall-clock seconds per watch session
MAX_REPL_LINES = 10000            # max input lines per interactive session

FRAME_TYPES = {"frame", "page", "screen", "artboard", "canvas"}


def slugify(name: str) -> str:
    """Convert a frame name into a filesystem-safe slug (lowercase, dashes)."""
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower())
    slug = slug.strip("-")
    return slug or "unnamed"


def find_repo_root(marker: str = DEFAULT_DESIGN_REL) -> Optional[str]:
    """Walk up from cwd looking for a directory containing *marker*.

    Returns the repo-root directory path, or None if not found before `/`.
    """
    cur = os.path.abspath(os.getcwd())
    while True:
        if os.path.exists(os.path.join(cur, marker)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def resolve_design_path(path: Optional[str] = None) -> str:
    """Resolve a design file path relative to the repo root when possible.

    Absolute paths pass through unchanged. Relative paths are resolved against
    the repo root (found by walking up from cwd until DEFAULT_DESIGN_REL
    exists); if no repo root is found, fall back to cwd-relative abspath.
    PID/PORT files intentionally keep using cwd and are NOT affected.
    """
    p = path or DEFAULT_DESIGN_REL
    if os.path.isabs(p):
        return p
    root = find_repo_root()
    if root is not None:
        return os.path.join(root, p)
    return os.path.abspath(p)


def _unwrap_inspect(payload: Any) -> Any:
    """Unwrap common JSON-RPC envelopes to reach the document tree."""
    seen = 0
    while isinstance(payload, dict) and seen < 3:
        if "result" in payload and len(payload) <= 3:
            payload = payload["result"]
            seen += 1
            continue
        if "inspection" in payload and len(payload) <= 5:
            payload = payload["inspection"]
            seen += 1
            continue
        break
    return payload


def _as_float(value: Any) -> Optional[float]:
    try:
        if isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounds_of(node: Dict[str, Any]) -> Tuple[Any, Any, Any, Any]:
    """Extract (x, y, w, h) from the many shapes inspect payloads may use."""
    x = y = w = h = None
    for src in (node, node.get("bounds") if isinstance(node.get("bounds"), dict) else {},
                node.get("rect") if isinstance(node.get("rect"), dict) else {},
                node.get("layout") if isinstance(node.get("layout"), dict) else {}):
        if not isinstance(src, dict):
            continue
        if x is None:
            x = _as_float(src.get("x", src.get("left")))
        if y is None:
            y = _as_float(src.get("y", src.get("top")))
        if w is None:
            w = _as_float(src.get("w", src.get("width")))
        if h is None:
            h = _as_float(src.get("h", src.get("height")))
    return x, y, w, h


def _looks_like_frame(node: Dict[str, Any]) -> bool:
    ntype = str(node.get("type", "")).strip().lower()
    if ntype in FRAME_TYPES:
        return True
    # Heuristic fallback: named node with bounds-like keys and frame-ish container keys.
    if "id" in node and "name" in node:
        keys = set(node.keys())
        if keys & {"x", "y", "width", "height", "w", "h", "bounds", "rect", "children", "screens"}:
            return True
    return False


def _top_keys(payload: Any, limit: int = 20) -> List[str]:
    if isinstance(payload, dict):
        return sorted(str(k) for k in payload.keys())[:limit]
    return [type(payload).__name__]


def extract_frames(inspect_payload: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Heuristically collect screen-level frames from a document.inspect payload.

    Returns (frames, debug) where frames is [{id, name, x, y, w, h}, ...] and
    debug carries {"checked": <top-level keys>} for error messages.
    """
    tree = _unwrap_inspect(inspect_payload)
    frames: List[Dict[str, Any]] = []
    visited = 0

    def walk(obj: Any, depth: int = 0) -> None:
        nonlocal visited
        if depth > 25 or visited > 20000:
            return
        visited += 1
        if isinstance(obj, dict):
            if _looks_like_frame(obj):
                x, y, w, h = _bounds_of(obj)
                frames.append({
                    "id": obj.get("id"),
                    "name": obj.get("name"),
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                })
            for key in ("frames", "screens", "pages", "children", "nodes", "document", "layers"):
                child = obj.get(key)
                if isinstance(child, (dict, list)):
                    walk(child, depth + 1)
            # Generic descent for unknown shapes (avoid re-walking known keys twice is fine).
            for key, child in obj.items():
                if key in ("frames", "screens", "pages", "children", "nodes", "document", "layers"):
                    continue
                if isinstance(child, (dict, list)):
                    walk(child, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, depth + 1)

    walk(tree)
    # Drop entries without any usable id.
    frames = [f for f in frames if f.get("id") is not None]
    debug = {"checked": _top_keys(tree)}
    return frames, debug


def _find_node(obj: Any, wanted: str, depth: int = 0) -> Optional[Dict[str, Any]]:
    """Depth-first search for a node whose id matches *wanted* (string-compared)."""
    if depth > 25:
        return None
    if isinstance(obj, dict):
        if "id" in obj and str(obj.get("id")) == wanted:
            return obj
        for child in obj.values():
            if isinstance(child, (dict, list)):
                found = _find_node(child, wanted, depth + 1)
                if found is not None:
                    return found
        return None
    if isinstance(obj, list):
        for item in obj:
            found = _find_node(item, wanted, depth + 1)
            if found is not None:
                return found
        return None
    return None


def summarize_node(node: Dict[str, Any]) -> Dict[str, Any]:
    """Build a compact property summary of a node for mutation verification."""
    x, y, w, h = _bounds_of(node)
    summary: Dict[str, Any] = {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
        "x": x,
        "y": y,
        "w": w,
        "h": h,
    }
    for key in ("fill", "fills", "stroke", "strokes", "text", "characters",
                "fontSize", "visible", "opacity"):
        if key in node:
            summary[key] = node[key]
    return summary


def friendly_json_error(err: Exception, example: str = '{"key": "value"}') -> str:
    """Render a human-friendly JSON parse error with position + example."""
    msg = str(err)
    pos: Optional[int] = getattr(err, "pos", None)
    lineno: Optional[int] = getattr(err, "lineno", None)
    colno: Optional[int] = getattr(err, "colno", None)
    where = ""
    if lineno is not None and colno is not None:
        where = f" at line {lineno}, column {colno}"
    elif pos is not None:
        where = f" at character {pos}"
    return (f"Invalid JSON{where}: {msg}. "
            f"Example: exec <command> '{example}'")


class FigcraftTerminal:
    def __init__(self, port: int = DEFAULT_PORT, host: str = "127.0.0.1", timeout: float = 5.0):
        self.port = port
        self.host = host
        self.timeout = timeout

    def is_port_listening(self) -> bool:
        """Check if FigCraft control port is actively listening."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            s.connect((self.host, self.port))
            s.close()
            return True
        except Exception:
            return False

    def send_rpc(self, method: str, params: Optional[Dict[str, Any]] = None, req_id: int = 1) -> Dict[str, Any]:
        """Send a single JSON-RPC 2.0 command over the TCP socket."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        try:
            s.connect((self.host, self.port))
        except Exception as e:
            return {"ok": False, "error": f"Cannot connect to FigCraft at {self.host}:{self.port} ({e})"}

        payload = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            payload["params"] = params

        data_bytes = (json.dumps(payload) + "\n").encode("utf-8")
        s.sendall(data_bytes)

        buf = b""
        # Bounded read: socket timeout + hard chunk cap (cut-loop guard).
        for _ in range(MAX_SOCKET_CHUNKS):
            try:
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
                if b"\n" in buf:
                    break
            except socket.timeout:
                break
        s.close()

        if not buf:
            return {"ok": False, "error": "No response from FigCraft socket"}

        try:
            return json.loads(buf.decode("utf-8"))
        except Exception as e:
            return {"ok": False, "error": f"Invalid JSON response: {e}", "raw": buf.decode("utf-8", errors="replace")}

    def execute_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute one of FigCraft's 569 built-in engine commands."""
        return self.send_rpc("engine.execute", {"command": command, "params": params or {}})

    def start_server(self, file_path: Optional[str] = None, wait_ready: bool = True) -> Dict[str, Any]:
        """Launch FigCraft with the requested control port and automation flags."""
        if self.is_port_listening():
            return {
                "ok": True,
                "status": "already_running",
                "port": self.port,
                "message": f"FigCraft control port {self.port} is already active and responsive."
            }

        app_bin = DEFAULT_APP_PATH
        if not os.path.exists(app_bin):
            return {
                "ok": False,
                "error": f"FigCraft binary not found at {app_bin}. Ensure FigCraft.app is installed in /Applications."
            }

        cwd = os.getcwd()
        cmd = [
            app_bin,
            "--control", str(self.port),
            "--automation-read-root", cwd,
            "--automation-write-root", cwd,
        ]
        if file_path:
            abs_file = resolve_design_path(file_path)
            cmd.append(abs_file)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))
        with open(PORT_FILE, "w") as f:
            f.write(str(self.port))

        if wait_ready:
            start_time = time.time()
            ready = False
            while time.time() - start_time < 10.0:
                if self.is_port_listening():
                    ready = True
                    break
                time.sleep(0.3)

            if not ready:
                return {
                    "ok": False,
                    "error": f"FigCraft launched (PID {proc.pid}) but port {self.port} did not respond within 10s."
                }

        return {
            "ok": True,
            "status": "started",
            "pid": proc.pid,
            "port": self.port,
            "file": file_path or "(none)",
            "message": f"FigCraft started successfully on port {self.port} (PID {proc.pid})."
        }

    def stop_server(self) -> Dict[str, Any]:
        """Gracefully terminate running FigCraft daemon."""
        pid = None
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE) as f:
                    pid = int(f.read().strip())
            except Exception:
                pass

        stopped = False
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)
                stopped = True
            except ProcessLookupError:
                stopped = True
            except Exception as e:
                return {"ok": False, "error": f"Failed to kill PID {pid}: {e}"}

        for fpath in [PID_FILE, PORT_FILE]:
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass

        return {
            "ok": True,
            "status": "stopped",
            "pid": pid,
            "message": "FigCraft process terminated and lockfiles cleared."
        }

    def status(self) -> Dict[str, Any]:
        """Check live health and get active document inspection."""
        listening = self.is_port_listening()
        pid = None
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE) as f:
                    pid = int(f.read().strip())
            except Exception:
                pass

        if not listening:
            return {
                "ok": False,
                "listening": False,
                "port": self.port,
                "pid": pid,
                "message": f"Port {self.port} is inactive. Use 'start' to launch FigCraft."
            }

        inspect_res = self.send_rpc("document.inspect")
        return {
            "ok": True,
            "listening": True,
            "port": self.port,
            "pid": pid,
            "inspection": inspect_res.get("result", inspect_res)
        }

    def list_frames(self) -> Dict[str, Any]:
        """Return screen-level frames (id, name, x/y/w/h) via document.inspect."""
        inspect_res = self.send_rpc("document.inspect")
        if not inspect_res.get("ok", True) and inspect_res.get("error"):
            return {"ok": False, "error": inspect_res.get("error"), "engine_result": inspect_res}
        frames, debug = extract_frames(inspect_res)
        if not frames:
            return {
                "ok": False,
                "error": "No screen-level frames recognized in document.inspect response.",
                "hint": "Expected nodes with type frame/page/screen (or named nodes with x/y/w/h).",
                "top_keys": debug.get("checked", []),
                "engine_result": inspect_res,
            }
        return {"ok": True, "count": len(frames), "frames": frames}

    def export_frame(self, node_id: int, out_path: str, fmt: str = "png", scale: float = 1.0) -> Dict[str, Any]:
        """Select a frame and export it cleanly to disk."""
        abs_out = os.path.abspath(out_path)
        parent = os.path.dirname(abs_out)
        if parent:
            os.makedirs(parent, exist_ok=True)

        self.execute_command("select.set", {"ids": [node_id]})
        res = self.execute_command("file.export", {
            "path": abs_out,
            "ids": [node_id],
            "format": fmt,
            "scale": scale
        })

        success = res.get("ok", False) and os.path.exists(abs_out)
        bytes_len = os.path.getsize(abs_out) if success else 0
        return {
            "ok": success,
            "node_id": node_id,
            "format": fmt,
            "scale": scale,
            "path": abs_out,
            "bytes": bytes_len,
            "engine_result": res
        }

    def export_all(self, out_dir: str, fmt: str = "png", scale: float = 1.0,
                   prefix: str = "") -> Dict[str, Any]:
        """Export every screen-level frame to <dir>/<slug>.<ext>; skip unnamed ones."""
        frames_res = self.list_frames()
        if not frames_res.get("ok"):
            return frames_res
        os.makedirs(os.path.abspath(out_dir), exist_ok=True)
        exported: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        for fr in frames_res["frames"]:
            name = fr.get("name")
            if not name or not str(name).strip():
                skipped.append({"id": fr.get("id"), "reason": "missing or blank frame name"})
                continue
            fname = f"{prefix}{slugify(str(name))}.{fmt}"
            out_path = os.path.join(os.path.abspath(out_dir), fname)
            res = self.export_frame(fr["id"], out_path, fmt=fmt, scale=scale)
            if res.get("ok"):
                exported.append({"id": fr.get("id"), "name": name, "path": res["path"]})
            else:
                skipped.append({"id": fr.get("id"), "name": name,
                                "reason": res.get("engine_result", res)})
        return {"ok": True, "count": len(exported), "exported": exported, "skipped": skipped}

    def diff_node(self, node_id: Any) -> Dict[str, Any]:
        """Return a compact property summary of one node for mutation verification."""
        inspect_res = self.send_rpc("document.inspect")
        if not inspect_res.get("ok", True) and inspect_res.get("error"):
            return {"ok": False, "error": inspect_res.get("error"), "engine_result": inspect_res}
        tree = _unwrap_inspect(inspect_res)
        node = _find_node(tree, str(node_id))
        if node is None:
            return {"ok": False, "error": f"Node id {node_id!r} not found in document.inspect.",
                    "top_keys": _top_keys(tree)}
        return {"ok": True, "node": summarize_node(node)}

    def reload_file(self, file_path: Optional[str] = None, mode: str = "soft") -> Dict[str, Any]:
        """Reload a file: soft refresh when supported, else legacy close+open fallback.

        mode="soft" (default) tries an in-place refresh without force-closing the
        tab and falls back to the legacy behavior with "fallback": true when the
        engine does not support it. mode="hard" always uses legacy close+open.
        A soft path that the engine rejects is NOT fatal — it falls back.
        """
        p = resolve_design_path(file_path)
        if mode == "hard":
            self.execute_command("file.close", {"force": True})
            res = self.execute_command("file.open", {"path": p})
            if isinstance(res, dict):
                res = dict(res)
                res["fallback"] = False
            return res
        # Soft: try refresh-style engine commands first.
        soft_attempts = [
            ("file.reload", {"path": p}),
            ("file.refresh", {"path": p}),
            ("document.refresh", {}),
        ]
        last: Optional[Dict[str, Any]] = None
        for cmd, params in soft_attempts:
            try:
                res = self.execute_command(cmd, params)
            except Exception as e:
                last = {"ok": False, "error": str(e)}
                continue
            if isinstance(res, dict) and res.get("ok"):
                out = dict(res)
                out["fallback"] = False
                out["mode"] = "soft"
                return out
            last = res
        # Fallback to legacy behavior; not fatal.
        self.execute_command("file.close", {"force": True})
        res = self.execute_command("file.open", {"path": p})
        out = dict(res) if isinstance(res, dict) else {"ok": False, "error": "empty engine response"}
        out["fallback"] = True
        out["mode"] = "soft"
        out["soft_error"] = last
        return out

    def watch_file(self, file_path: Optional[str] = None, out_dir: str = ".",
                   debounce: float = 0.5, fmt: str = "png", scale: float = 1.0,
                   prefix: str = "", on_event: Optional[Any] = None,
                   max_events: int = MAX_WATCH_EVENTS,
                   max_seconds: float = MAX_WATCH_SECONDS) -> Dict[str, Any]:
        """Poll mtime; on each change run soft reload + export-all (stdlib only).

        Stops on Ctrl-C, on ``max_events`` changes, or after ``max_seconds`` —
        every watch session is bounded (cut-loop guard).
        """
        p = resolve_design_path(file_path)
        last_mtime: Optional[float] = None
        try:
            last_mtime = os.path.getmtime(p)
        except OSError:
            last_mtime = None
        events = 0
        errors: List[Any] = []
        deadline = time.monotonic() + max(1.0, max_seconds)
        stop_reason = "completed"
        try:
            while events < max(1, max_events) and time.monotonic() < deadline:
                time.sleep(max(debounce, 0.05))
                try:
                    mtime = os.path.getmtime(p)
                except OSError:
                    continue
                if last_mtime is None:
                    last_mtime = mtime
                    continue
                if mtime != last_mtime:
                    last_mtime = mtime
                    events += 1
                    reload_res = self.reload_file(p, mode="soft")
                    export_res = self.export_all(out_dir, fmt=fmt, scale=scale, prefix=prefix)
                    info = {"event": events, "file": p,
                            "reload": reload_res, "export": export_res}
                    if on_event is not None:
                        on_event(info)
                    else:
                        print(json.dumps(info))
        except KeyboardInterrupt:
            stop_reason = "interrupted"
        if events >= max(1, max_events):
            stop_reason = "max_events"
        elif time.monotonic() >= deadline:
            stop_reason = "max_seconds"
        summary = {"ok": True, "events": events, "file": p, "stop": stop_reason,
                   "out_dir": os.path.abspath(out_dir), "errors": errors}
        return summary


# ---------------------------------------------------------------------------
# CLI & AGENT REPL
# ---------------------------------------------------------------------------
REPL_HELP = (
    "Commands:\n"
    "  status                 Check socket health and active document\n"
    "  inspect                Raw document.inspect output\n"
    "  frames                 List screen-level frames (id, name, x/y/w/h)\n"
    "  open <path>            Open a file in running FigCraft\n"
    "  reload [--soft|--hard] [file]  Reload file (default --soft with fallback)\n"
    "  export <id> <path>     Export one node to image\n"
    "  export-all <dir> [--format png] [--scale 1.0] [--prefix \"\"]\n"
    "                         Export all frames to a directory\n"
    "  diff <id>              Show property summary of one node\n"
    "  exec <cmd> [json]      Execute an engine command\n"
    "  watch <file> -o <dir>  Poll mtime; reload+export on change (Ctrl-C stops)\n"
    "  history                Show session command history (!n re-runs entry n)\n"
    "  help [cmd]             This help, or per-command help\n"
    "  quit                   Exit the REPL"
)

REPL_CMD_HELP: Dict[str, str] = {
    "status": "status — check socket health and active document. No arguments.",
    "inspect": "inspect — print raw document.inspect output. No arguments.",
    "frames": "frames — list screen-level frames via document.inspect: id, name, x/y/w/h.",
    "open": "open <path> — open a .figcraft file in running FigCraft.",
    "reload": "reload [--soft|--hard] [file] — default --soft tries refresh without force-closing the tab, falls back to close+open with \"fallback\": true. --hard always closes+opens.",
    "export": "export <id> <path> — export one node to an image file.",
    "export-all": "export-all <dir> [--format png] [--scale 1.0] [--prefix \"\"] — export every frame to <dir>/<slug>.<ext>.",
    "diff": "diff <id> — property summary (id, name, type, x/y/w/h, fill/stroke/text) for verifying mutations.",
    "exec": "exec <cmd> [json] — execute an engine command, e.g. exec file.save '{\"path\": \"out.figcraft\"}'.",
    "watch": "watch <file> -o <dir> [--debounce 0.5] [--format png] — poll mtime, reload soft + export-all on change. Ctrl-C stops.",
    "history": "history — show session history. Use !n to re-run entry n.",
    "help": "help [cmd] — overall help or per-command help, e.g. help export-all.",
    "quit": "quit — exit the REPL (also: exit).",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FigCraft Agent Terminal — Live Socket & Process Bridge")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="TCP control port (default: 9880)")

    sub = parser.add_subparsers(dest="cmd", help="Action to execute")

    # start
    p_start = sub.add_parser("start", help="Start FigCraft with open live port")
    p_start.add_argument("--file", "-f", default=DEFAULT_DESIGN_REL,
                         help=f"File to open (resolved vs repo root; default: {DEFAULT_DESIGN_REL})")
    p_start.add_argument("--no-wait", action="store_true", help="Do not wait for port ready")

    # stop
    sub.add_parser("stop", help="Stop running FigCraft process")

    # status
    sub.add_parser("status", help="Check socket health and active document")

    # open
    p_open = sub.add_parser("open", help="Open a file in running FigCraft")
    p_open.add_argument("file", help="Path to .figcraft file (resolved vs repo root if relative)")

    # reload
    p_rel = sub.add_parser("reload", help="Reload file from disk (default --soft with fallback to close+open)")
    p_rel.add_argument("file", nargs="?", default=DEFAULT_DESIGN_REL,
                       help=f"File to reload (resolved vs repo root; default: {DEFAULT_DESIGN_REL})")
    grp = p_rel.add_mutually_exclusive_group()
    grp.add_argument("--soft", dest="mode", action="store_const", const="soft",
                     help="Refresh without force-closing the tab; fall back if unsupported (default)")
    grp.add_argument("--hard", dest="mode", action="store_const", const="hard",
                     help="Legacy behavior: file.close force + file.open")
    p_rel.set_defaults(mode="soft")

    # exec
    p_exec = sub.add_parser("exec", help="Execute an engine command (params must be valid JSON)")
    p_exec.add_argument("command", help="Command name (e.g. file.save, select.set, node.set)")
    p_exec.add_argument("params", nargs="?", default="{}", help="JSON parameters, e.g. '{\"ids\": [1]}'")

    # export
    p_exp = sub.add_parser("export", help="Export a single node to an image file")
    p_exp.add_argument("--id", type=int, required=True, help="Node ID")
    p_exp.add_argument("--out", "-o", required=True, help="Output image file path")
    p_exp.add_argument("--format", default="png", choices=["png", "svg", "pdf", "webp"], help="Image format (default: png)")
    p_exp.add_argument("--scale", type=float, default=1.0, help="Export scale (default: 1.0)")

    # frames
    p_frames = sub.add_parser("frames", help="List screen-level frames via document.inspect (id, name, x/y/w/h)")
    p_frames.add_argument("--json", action="store_true",
                          help="Output JSON (default output is already JSON; kept for compatibility)")

    # export-all
    p_ea = sub.add_parser("export-all", help="Export every screen-level frame to a directory")
    p_ea.add_argument("--out", "-o", required=True, help="Output directory")
    p_ea.add_argument("--format", default="png", choices=["png", "svg", "pdf", "webp"],
                      help="Image format (default: png)")
    p_ea.add_argument("--scale", type=float, default=1.0, help="Export scale (default: 1.0)")
    p_ea.add_argument("--prefix", default="", help="Filename prefix (default: empty)")

    # diff
    p_diff = sub.add_parser("diff", help="Show property summary of one node (verify mutations without raw inspect)")
    p_diff.add_argument("--id", required=True, help="Node ID")

    # watch
    p_watch = sub.add_parser("watch", help="Poll file mtime; on change run soft reload + export-all (Ctrl-C stops)")
    p_watch.add_argument("file", help="File to watch (resolved vs repo root if relative)")
    p_watch.add_argument("--out", "-o", required=True, help="Export directory for export-all on each change")
    p_watch.add_argument("--debounce", type=float, default=0.5, help="Poll interval in seconds (default: 0.5)")
    p_watch.add_argument("--format", default="png", choices=["png", "svg", "pdf", "webp"],
                         help="Image format (default: png)")
    p_watch.add_argument("--scale", type=float, default=1.0, help="Export scale (default: 1.0)")
    p_watch.add_argument("--prefix", default="", help="Filename prefix (default: empty)")
    p_watch.add_argument("--max-events", type=int, default=MAX_WATCH_EVENTS,
                         help=f"Stop after N changes (default: {MAX_WATCH_EVENTS})")
    p_watch.add_argument("--max-seconds", type=float, default=MAX_WATCH_SECONDS,
                         help=f"Stop after N seconds (default: {MAX_WATCH_SECONDS})")

    # interactive REPL
    sub.add_parser("interactive", help="Start interactive terminal REPL session")

    # harness-info
    sub.add_parser("harness-info", help="Output JSON descriptor for AI harnesses")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    term = FigcraftTerminal(port=args.port)

    if args.cmd == "start":
        res = term.start_server(file_path=args.file, wait_ready=not args.no_wait)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("ok") else 1)

    elif args.cmd == "stop":
        res = term.stop_server()
        print(json.dumps(res, indent=2))

    elif args.cmd == "status":
        res = term.status()
        print(json.dumps(res, indent=2))

    elif args.cmd == "open":
        abs_p = resolve_design_path(args.file)
        res = term.execute_command("file.open", {"path": abs_p})
        print(json.dumps(res, indent=2))

    elif args.cmd == "reload":
        res = term.reload_file(args.file, mode=args.mode)
        print(json.dumps(res, indent=2))

    elif args.cmd == "exec":
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(json.dumps({"ok": False, "error": friendly_json_error(e)}))
            sys.exit(1)
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"Invalid JSON params: {e}"}))
            sys.exit(1)
        res = term.execute_command(args.command, params)
        print(json.dumps(res, indent=2))

    elif args.cmd == "export":
        res = term.export_frame(args.id, args.out, fmt=args.format, scale=args.scale)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("ok") else 1)

    elif args.cmd == "frames":
        res = term.list_frames()
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("ok") else 1)

    elif args.cmd == "export-all":
        res = term.export_all(args.out, fmt=args.format, scale=args.scale, prefix=args.prefix)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("ok") else 1)

    elif args.cmd == "diff":
        res = term.diff_node(args.id)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res.get("ok") else 1)

    elif args.cmd == "watch":
        try:
            res = term.watch_file(args.file, out_dir=args.out, debounce=args.debounce,
                                  fmt=args.format, scale=args.scale, prefix=args.prefix,
                                  max_events=args.max_events, max_seconds=args.max_seconds)
        except KeyboardInterrupt:
            res = {"ok": True, "events": 0, "interrupted": True}
        print(json.dumps(res, indent=2))

    elif args.cmd == "harness-info":
        design = load_design()
        manifest = {
            "name": HARNESS_NAME,
            "version": HARNESS_VERSION,
            "design_contract": design["$schema"],
            "style_direction": design["style_direction"],
            "theme": design.get("default_theme", "dark"),
            "protocol": "TCP JSON-RPC 2.0",
            "default_port": DEFAULT_PORT,
            "port_active": term.is_port_listening(),
            "capabilities": [
                "start_server",
                "stop_server",
                "inspect_document",
                "open_file",
                "execute_engine_command",
                "export_frame",
                "export_all_frames",
                "list_frames",
                "diff_node",
                "soft_reload_with_fallback",
                "watch_file_mtime",
                "repl_history",
                "interactive_repl"
            ],
            "commands": {
                "start": "python3 scripts/agent_terminal.py start [--port PORT] [--file FILE]",
                "status": "python3 scripts/agent_terminal.py status [--port PORT]",
                "frames": "python3 scripts/agent_terminal.py frames [--port PORT]",
                "exec": "python3 scripts/agent_terminal.py exec <command> [params_json]",
                "export": "python3 scripts/agent_terminal.py export --id <id> -o <path>",
                "export-all": "python3 scripts/agent_terminal.py export-all -o <dir> [--format png] [--scale 1.0]",
                "reload": "python3 scripts/agent_terminal.py reload [file] [--soft|--hard]",
                "diff": "python3 scripts/agent_terminal.py diff --id <n>",
                "watch": "python3 scripts/agent_terminal.py watch <file> -o <dir> [--debounce 0.5] [--max-events N] [--max-seconds S]",
                "stop": "python3 scripts/agent_terminal.py stop"
            }
        }
        print(json.dumps(manifest, indent=2))

    elif args.cmd == "interactive":
        print(f"=== FigCraft Agent Terminal REPL (Port {args.port}) ===")
        print(REPL_HELP)
        history: List[str] = []

        def run_line(line: str) -> None:
            parts = line.split(maxsplit=2)
            action = parts[0]
            if action == "status":
                print(json.dumps(term.status(), indent=2))
            elif action == "inspect":
                print(json.dumps(term.send_rpc("document.inspect"), indent=2))
            elif action == "frames":
                print(json.dumps(term.list_frames(), indent=2))
            elif action == "open" and len(parts) > 1:
                print(json.dumps(term.execute_command("file.open", {"path": resolve_design_path(parts[1])}), indent=2))
            elif action == "reload":
                toks = parts[1:] + (parts[2].split() if len(parts) > 2 else [])
                mode = "soft"
                target: Optional[str] = None
                for t in (" ".join(toks)).split():
                    if t == "--soft":
                        mode = "soft"
                    elif t == "--hard":
                        mode = "hard"
                    elif not t.startswith("--"):
                        target = t
                print(json.dumps(term.reload_file(target or DEFAULT_DESIGN_REL, mode=mode), indent=2))
            elif action == "export" and len(parts) > 2:
                print(json.dumps(term.export_frame(int(parts[1]), parts[2]), indent=2))
            elif action == "export-all" and len(parts) > 1:
                rest = (" ".join(parts[1:])).split()
                out_dir = rest[0]
                fmt, scale, prefix = "png", 1.0, ""
                i = 1
                while i < len(rest):
                    if rest[i] == "--format" and i + 1 < len(rest):
                        fmt = rest[i + 1]
                        i += 2
                    elif rest[i] == "--scale" and i + 1 < len(rest):
                        scale = float(rest[i + 1])
                        i += 2
                    elif rest[i] == "--prefix" and i + 1 < len(rest):
                        prefix = rest[i + 1]
                        i += 2
                    else:
                        i += 1
                print(json.dumps(term.export_all(out_dir, fmt=fmt, scale=scale, prefix=prefix), indent=2))
            elif action == "diff" and len(parts) > 1:
                print(json.dumps(term.diff_node(parts[1]), indent=2))
            elif action == "exec" and len(parts) > 1:
                try:
                    p = json.loads(parts[2]) if len(parts) > 2 else {}
                except json.JSONDecodeError as e:
                    print(json.dumps({"ok": False, "error": friendly_json_error(e)}))
                    return
                print(json.dumps(term.execute_command(parts[1], p), indent=2))
            elif action == "watch":
                print(json.dumps({"ok": False, "error": "Usage: watch <file> -o <dir> [--debounce 0.5] [--format png]"}))
            elif action == "history":
                for n, h in enumerate(history, 1):
                    print(f"{n}: {h}")
            elif action in ("help", "?"):
                if len(parts) > 1 and parts[1] in REPL_CMD_HELP:
                    print(REPL_CMD_HELP[parts[1]])
                else:
                    print(REPL_HELP)
            else:
                print("Unknown command. Type 'help'.")

        # Bounded REPL: never loop forever on a scripted stdin stream.
        for _ in range(MAX_REPL_LINES):
            try:
                line = input("figcraft> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line in ["quit", "exit"]:
                break
            if line.startswith("!"):
                try:
                    n = int(line[1:])
                    line = history[n - 1]
                    print(f"figcraft> {line}")
                except (ValueError, IndexError):
                    print(f"Unknown history entry {line!r}. Type 'history'.")
                    continue
            if line in ["help", "?"]:
                print(REPL_HELP)
                history.append(line)
                continue
            if line.split(maxsplit=1)[0] in ("help", "?") and len(line.split()) > 1:
                key = line.split()[1]
                print(REPL_CMD_HELP.get(key, REPL_HELP))
                history.append(line)
                continue
            history.append(line)
            parts0 = line.split(maxsplit=1)
            if parts0[0] == "watch":
                # watch <file> -o <dir> [--debounce X] [--format F] [--scale S] [--prefix P]
                import shlex
                try:
                    toks = shlex.split(line)[1:]
                except ValueError as e:
                    print(json.dumps({"ok": False, "error": f"Cannot parse watch args: {e}"}))
                    continue
                wfile: Optional[str] = None
                wout: Optional[str] = None
                deb, wfmt, wscale, wprefix = 0.5, "png", 1.0, ""
                i = 0
                while i < len(toks):
                    t = toks[i]
                    if t in ("-o", "--out") and i + 1 < len(toks):
                        wout = toks[i + 1]
                        i += 2
                    elif t == "--debounce" and i + 1 < len(toks):
                        deb = float(toks[i + 1])
                        i += 2
                    elif t == "--format" and i + 1 < len(toks):
                        wfmt = toks[i + 1]
                        i += 2
                    elif t == "--scale" and i + 1 < len(toks):
                        wscale = float(toks[i + 1])
                        i += 2
                    elif t == "--prefix" and i + 1 < len(toks):
                        wprefix = toks[i + 1]
                        i += 2
                    elif not t.startswith("-") and wfile is None:
                        wfile = t
                        i += 1
                    else:
                        i += 1
                if not wfile or not wout:
                    print(json.dumps({"ok": False, "error": "Usage: watch <file> -o <dir> [--debounce 0.5] [--format png]"}))
                    continue
                try:
                    summary = term.watch_file(wfile, out_dir=wout, debounce=deb,
                                              fmt=wfmt, scale=wscale, prefix=wprefix)
                except KeyboardInterrupt:
                    summary = {"ok": True, "events": 0, "interrupted": True}
                print(json.dumps(summary, indent=2))
                continue
            try:
                run_line(line)
            except (EOFError, KeyboardInterrupt):
                print()
                break
            except Exception as e:
                print(json.dumps({"ok": False, "error": str(e)}))


if __name__ == "__main__":
    main()
