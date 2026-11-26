#!/usr/bin/env python3
"""
FigCraft Multi-Agent Concurrency Orchestrator (kuron-design-figcraft 3.2.2)
Demonstrates and manages concurrent multi-agent design workflows on a single .figcraft file.
Compatible with Antigravity, Claude Code, Muse Code, and OMP.

Supports 3 concurrent operational modes:
1. LIVE SOCKET MULTIPLEXING: Concurrent subagents connect via TCP JSON-RPC to a running
   FigCraft instance (--control <port>). Rust engine serializes atomic AST mutations.
2. PARTITIONED AST MERGING: Subagents work offline on isolated Node ID namespaces (e.g. 1000+, 2000+)
   and merge into the root document.json with atomic file locks and zero collision.
3. CRDT REAL-TIME COLLAB: Vector-clock synchronization using FigCraft's native collab protocol.
"""

import sys
import os
import json
import socket
import tempfile
import zipfile
import argparse
import threading
import time
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness_detect import detect_harness  # noqa: E402

MAX_LOCK_RETRIES = 100  # cut-loop guard for lock acquisition
LOCK_POLL_SECONDS = 0.05
LOCK_STALE_SECONDS = 30.0   # a lock with no live owner older than this is stale
MAX_ZIP_ENTRIES = 256       # bound work on untrusted .figcraft containers


class MultiAgentSocketWorker:
    """
    Subagent client that connects to FigCraft's live JSON-RPC socket server.
    Multiple instances can execute simultaneously across different frames without race conditions.
    """

    def __init__(self, agent_id: str, frame_id: int, port: int = 9880,
                 timeout: float = 5.0):
        self.agent_id = agent_id
        self.frame_id = frame_id
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect(("127.0.0.1", self.port))
            return True
        except Exception as e:
            print(f"[{self.agent_id}] Failed to connect: {e}")
            if self.sock is not None:
                try:
                    self.sock.close()
                except OSError:
                    pass
                self.sock = None
            return False

    def rpc(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.sock:
            raise ConnectionError("Worker not connected")
        payload = {
            "id": int(time.time() * 1000) % 100000,
            "method": "engine.execute",
            "params": {"command": command, "params": params or {}}
        }
        self.sock.sendall(json.dumps(payload).encode() + b"\n")
        buf = b""
        # Socket timeout + hard chunk cap = bounded read (cut-loop guard).
        for _ in range(1024):
            chunk = self.sock.recv(16384)
            if not chunk:
                break
            buf += chunk
            if b"\n" in buf:
                break
        return json.loads(buf.decode())

    def update_frame_title(self, new_title: str):
        """Live mutate a frame property atomically."""
        res = self.rpc("node.set", {
            "id": self.frame_id,
            "properties": {"name": new_title}
        })
        print(f"[{self.agent_id}] Live updated node {self.frame_id} -> '{new_title}': {res.get('ok')}")
        return res

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None


class ASTPartitionMerger:
    """
    Offline/File-based concurrency:
    Allows multiple subagents to generate independent screen subtrees using partitioned ID spaces.
    Merges their dictionaries into master document.json under a bounded, recoverable lock.
    """

    def __init__(self, master_path: str):
        self.master_path = master_path
        self.lock_path = master_path + ".lock"
        self._lock_token: Optional[str] = None

    def _lock_identity(self) -> Optional[Tuple[int, str]]:
        """Read ``pid:token`` from the lock file, or None if it is malformed."""
        try:
            with open(self.lock_path, "r", encoding="utf-8") as handle:
                pid_str, _, token = handle.read().strip().partition(":")
            return int(pid_str), token
        except (OSError, ValueError):
            return None

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        """Check whether the recorded owner process still exists."""
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True   # exists but owned by another user
        except OSError:
            return False
        return True

    def _lock_is_old(self) -> bool:
        try:
            return time.time() - os.path.getmtime(self.lock_path) > LOCK_STALE_SECONDS
        except OSError:
            return False

    def _clear_stale_lock(self) -> bool:
        """Remove a lock whose owner is gone, or an old unreadable lock."""
        identity = self._lock_identity()
        if identity is None:
            stale = self._lock_is_old()
        else:
            stale = not self._pid_alive(identity[0])
        if not stale:
            return False
        try:
            os.remove(self.lock_path)
            return True
        except OSError:
            return False

    def acquire_lock(self, timeout: float = 5.0) -> bool:
        """Acquire the merge lock with a monotonic deadline and stale recovery."""
        deadline = time.monotonic() + max(0.0, timeout)
        token = "%d:%s" % (os.getpid(), os.urandom(8).hex())
        for _ in range(MAX_LOCK_RETRIES):  # cut-loop guard
            if time.monotonic() >= deadline:
                break
            try:
                # O_EXCL ensures atomic lock creation.
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                self._clear_stale_lock()
                remaining = max(0.0, deadline - time.monotonic())
                time.sleep(min(LOCK_POLL_SECONDS, remaining))
                continue
            except OSError:
                break
            try:
                os.write(fd, token.encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
            self._lock_token = token
            return True
        return False

    def release_lock(self) -> None:
        """Release only a lock this instance still owns (idempotent)."""
        token = self._lock_token
        self._lock_token = None
        if token is None:
            return
        try:
            with open(self.lock_path, "r", encoding="utf-8") as handle:
                if handle.read().strip() != token:
                    return   # ownership changed; never delete another owner's lock
            os.remove(self.lock_path)
        except OSError:
            pass

    @staticmethod
    def _default_page_id(doc: Dict[str, Any]) -> str:
        # Keep the historical root-page default when it exists, otherwise use
        # the document's first page.
        if "1" in (doc.get("nodes") or {}):
            return "1"
        pages = doc.get("pages") or [1]
        return str(pages[0])

    @staticmethod
    def _check_collisions(doc_nodes: Dict[str, Any],
                          prepared: List[Tuple[int, Dict[str, Any], str]]) -> None:
        """Reject duplicate IDs before any node is written (deterministic)."""
        collisions = []
        seen = set()
        for index, nodes, _page in prepared:
            for key, node in nodes.items():
                nid = str(key)
                if nid in doc_nodes:
                    collisions.append("%s (already in document)" % nid)
                elif nid in seen:
                    collisions.append("%s (subtree %d)" % (nid, index))
                seen.add(nid)
                if isinstance(node, dict) and "id" in node and str(node["id"]) != nid:
                    collisions.append("%s (id field disagrees with key)" % nid)
        if collisions:
            raise ValueError("node ID collision across merged partitions: "
                             + ", ".join(sorted(collisions)))

    def merge_subtrees(self, subtrees: List[Dict[str, Any]],
                       timeout: float = 5.0) -> bool:
        """Merge subagent node trees into the master ZIP container atomically.

        Each subtree may target a ``page``; untargeted subtrees land on the
        document's default root page. Sibling pages and every non-document ZIP
        entry are preserved verbatim.
        """
        if not self.acquire_lock(timeout):
            raise TimeoutError("Could not acquire file lock on .figcraft")

        try:
            with zipfile.ZipFile(self.master_path, "r") as z:
                infos = z.infolist()
                if len(infos) > MAX_ZIP_ENTRIES:
                    raise ValueError("too many .figcraft entries; refusing to merge")
                entries = [(info, z.read(info.filename)) for info in infos]
            doc_payload = next((data for info, data in entries
                                if info.filename == "document.json"), None)
            if doc_payload is None:
                raise ValueError("invalid .figcraft container: document.json is missing")
            doc = json.loads(doc_payload.decode("utf-8"))
            doc_nodes = doc.setdefault("nodes", {})

            prepared = []
            for index, st in enumerate(subtrees):
                nodes = st.get("nodes") or {}
                if not isinstance(nodes, dict):
                    raise ValueError("subtree %d has a non-mapping 'nodes' field" % index)
                page_id = str(st.get("page", self._default_page_id(doc)))
                prepared.append((index, nodes, page_id))
            self._check_collisions(doc_nodes, prepared)

            for _index, nodes, page_id in prepared:
                page = doc_nodes.get(page_id)
                if not isinstance(page, dict):
                    raise ValueError("merge target page %r not found in document" % page_id)
                children = page.setdefault("children", [])
                known = {str(child) for child in children}
                for nid, node in nodes.items():
                    doc_nodes[str(nid)] = node
                # The root of each subtree is attached only once.
                subtree = subtrees[_index]
                root_id = subtree.get("root_id")
                if root_id is not None and str(root_id) not in known:
                    children.append(root_id)
                    known.add(str(root_id))

            # Unique temp file in the target directory: no shared .tmp path and
            # os.replace() stays atomic on the same filesystem.
            target_dir = os.path.dirname(os.path.abspath(self.master_path))
            with tempfile.NamedTemporaryFile(
                    dir=target_dir, prefix=".figcraft-", suffix=".tmp",
                    delete=False) as handle:
                temp_path = handle.name
            try:
                with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as z_out:
                    for info, payload in entries:
                        if info.filename == "document.json":
                            payload = json.dumps(doc, separators=(",", ":")).encode("utf-8")
                        z_out.writestr(info.filename, payload,
                                       compress_type=info.compress_type)
                with open(temp_path, "rb+") as handle:
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self.master_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            print("[ASTMerger] Successfully merged %d agent subtrees into %s"
                  % (len(subtrees), self.master_path))
            return True
        finally:
            self.release_lock()


def simulate_concurrent_agents(out: Optional[str] = None):
    """Demonstrate two agents merging conflict-free into one .figcraft file.

    The builders are imported lazily so ``--help`` works from any directory
    without requiring the project's DESIGN.md.
    """
    from figcraft_tool import FigcraftDocument, TOKENS, hex_to_rgba  # noqa: E402

    print("=== Simulating 2 Concurrent Subagents on FigCraft Document ===")
    print("[Orchestrator] Runtime harness: %s" % detect_harness())

    # Setup base doc (output path is generic and overridable via CLI or env var)
    base_doc = FigcraftDocument("Collab Demo")
    demo_path = out or os.environ.get("FIGCRAFT_DEMO", "design/collab-demo.figcraft")
    parent = os.path.dirname(os.path.abspath(demo_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    base_doc.save(demo_path)

    # Subagent 1: Worker on Screen A (ID Range: 1000-1999)
    agent1_data = {}
    def agent1_task():
        print("[Agent-1] Generating Inspector Panel Tree (ID Space 1000-1999)...")
        nodes = {}
        nodes["1000"] = {
            "id": 1000,
            "name": "Screen A: Inspector Subagent",
            "type": "frame",
            "width": 600.0,
            "height": 800.0,
            "transform": [1.0, 0.0, 0.0, 1.0, 40.0, 40.0],
            "fills": [{"type": "solid", "color": hex_to_rgba(TOKENS["colors"]["surface"]), "opacity": 1.0, "visible": True}],
            "children": [1001],
            "layout": {"mode": "vertical", "gap": 10.0, "padding": [16.0, 16.0, 16.0, 16.0]}
        }
        nodes["1001"] = {
            "id": 1001,
            "name": "InspectorTitle",
            "type": "text",
            "text": "Generated by Subagent 1 (Claude Code / Antigravity)",
            "width": 400.0,
            "height": 24.0,
            "font_size": 14.0,
            "font_family": "Space Grotesk",
            "fills": [{"type": "solid", "color": hex_to_rgba(TOKENS["colors"]["action-primary"]), "opacity": 1.0, "visible": True}],
            "children": []
        }
        agent1_data["root_id"] = 1000
        agent1_data["nodes"] = nodes
        time.sleep(0.1)
        print("[Agent-1] Completed successfully!")

    # Subagent 2: Worker on Screen B (ID Range: 2000-2999)
    agent2_data = {}
    def agent2_task():
        print("[Agent-2] Generating Quota Estimator Modal (ID Space 2000-2999)...")
        nodes = {}
        nodes["2000"] = {
            "id": 2000,
            "name": "Screen B: Quota Estimator Subagent",
            "type": "frame",
            "width": 600.0,
            "height": 800.0,
            "transform": [1.0, 0.0, 0.0, 1.0, 680.0, 40.0],
            "fills": [{"type": "solid", "color": hex_to_rgba(TOKENS["colors"]["raised"]), "opacity": 1.0, "visible": True}],
            "children": [2001],
            "layout": {"mode": "vertical", "gap": 10.0, "padding": [16.0, 16.0, 16.0, 16.0]}
        }
        nodes["2001"] = {
            "id": 2001,
            "name": "EstimatorTitle",
            "type": "text",
            "text": "Generated by Subagent 2 (OMP / Muse Code)",
            "width": 400.0,
            "height": 24.0,
            "font_size": 14.0,
            "font_family": "Space Grotesk",
            "fills": [{"type": "solid", "color": hex_to_rgba(TOKENS["colors"]["data-technical"]), "opacity": 1.0, "visible": True}],
            "children": []
        }
        agent2_data["root_id"] = 2000
        agent2_data["nodes"] = nodes
        time.sleep(0.1)
        print("[Agent-2] Completed successfully!")

    # Launch threads concurrently
    t1 = threading.Thread(target=agent1_task)
    t2 = threading.Thread(target=agent2_task)
    t1.start()
    t2.start()
    t1.join(timeout=10.0)  # cut-loop guard: never wait forever on a worker
    t2.join(timeout=10.0)

    # Merge AST trees conflict-free
    merger = ASTPartitionMerger(demo_path)
    merger.merge_subtrees([agent1_data, agent2_data])

    print("✓ Collab test file generated and merged at:", demo_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demonstrate partitioned-ID multi-agent merging in FigCraft.")
    parser.add_argument(
        "--out", default=None,
        help="Output .figcraft path (default: FIGCRAFT_DEMO or design/collab-demo.figcraft).")
    parser.add_argument(
        "--show-harness", action="store_true",
        help="Print the detected runtime harness as JSON and exit.")
    args = parser.parse_args()
    if args.show_harness:
        print(json.dumps({"harness": detect_harness()}))
        return
    simulate_concurrent_agents(args.out)


if __name__ == "__main__":
    main()
