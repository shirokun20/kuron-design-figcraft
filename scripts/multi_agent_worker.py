#!/usr/bin/env python3
"""
FigCraft Multi-Agent Concurrency Orchestrator
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
import zipfile
import threading
import time
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figcraft_tool import FigcraftDocument, FigcraftClient, hex_to_rgba

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
        if self.sock:
            self.sock.close()


class ASTPartitionMerger:
    """
    Offline/File-based concurrency:
    Allows multiple subagents to generate independent screen subtrees using partitioned ID spaces.
    Merges their dictionaries into master document.json with atomic lock protection.
    """

    def __init__(self, master_path: str):
        self.master_path = master_path
        self.lock_path = master_path + ".lock"

    def acquire_lock(self, timeout: float = 5.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            try:
                # O_EXCL ensures atomic lock creation
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return True
            except FileExistsError:
                time.sleep(0.05)
        return False

    def release_lock(self):
        try:
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        except Exception:
            pass

    def merge_subtrees(self, subtrees: List[Dict[str, Any]]) -> bool:
        """
        Merge multiple subagent node trees into master document.json.
        Each subtree must have isolated node IDs to guarantee conflict-free merging.
        """
        if not self.acquire_lock():
            raise TimeoutError("Could not acquire file lock on .figcraft")

        try:
            # Read existing document
            with zipfile.ZipFile(self.master_path, "r") as z:
                doc = json.loads(z.read("document.json"))

            root_page = doc["nodes"]["1"]
            existing_children = set(root_page["children"])

            for st in subtrees:
                root_id = st["root_id"]
                nodes = st["nodes"]
                # Insert nodes
                for nid_str, node in nodes.items():
                    doc["nodes"][nid_str] = node
                # Add to root children if not present
                if root_id not in existing_children:
                    root_page["children"].append(root_id)
                    existing_children.add(root_id)

            # Write back atomically
            temp_path = self.master_path + ".tmp"
            with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as z_out:
                z_out.writestr("document.json", json.dumps(doc, indent=2))
            
            os.replace(temp_path, self.master_path)
            print(f"[ASTMerger] Successfully merged {len(subtrees)} agent subtrees into {self.master_path}")
            return True
        finally:
            self.release_lock()


def simulate_concurrent_agents():
    """
    Demonstration: 2 subagents concurrently generating Screen A and Screen B in parallel threads,
    then merging conflict-free into design/collab-demo.figcraft.
    """
    print("=== Simulating 2 Concurrent Subagents on FigCraft Document ===")

    # Setup base doc (output path is generic and overridable via env var)
    base_doc = FigcraftDocument("Collab Demo")
    demo_path = os.environ.get("FIGCRAFT_DEMO", "design/collab-demo.figcraft")
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
            "fills": [{"type": "solid", "color": hex_to_rgba("#141418"), "opacity": 1.0, "visible": True}],
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
            "fills": [{"type": "solid", "color": hex_to_rgba("#FF6B5A"), "opacity": 1.0, "visible": True}],
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
            "fills": [{"type": "solid", "color": hex_to_rgba("#22222A"), "opacity": 1.0, "visible": True}],
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
            "fills": [{"type": "solid", "color": hex_to_rgba("#35E7F5"), "opacity": 1.0, "visible": True}],
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
    t1.join()
    t2.join()

    # Merge AST trees conflict-free
    merger = ASTPartitionMerger(demo_path)
    merger.merge_subtrees([agent1_data, agent2_data])

    print("✓ Collab test file generated and merged at:", demo_path)

if __name__ == "__main__":
    simulate_concurrent_agents()
