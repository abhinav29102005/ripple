"""
Single-command launcher for Ripple.
Starts:
1. Five background autonomous agent workers (Watcher, Tracer, Statistician, Briefer, Librarian)
   coordinated by FalkorDB's coord graph via agents/runner.py.
2. FastAPI / Uvicorn server serving the dashboard and REST API endpoints.
Provides clean graceful shutdown on SIGINT (Ctrl+C) or SIGTERM.
"""
import os
import sys
import signal
import threading
import time
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import graph_manager
from coord import CoordEngine
from knowledge import KnowledgeEngine
from memory import TenantMemory
from config import settings

from agents.runner import WorkerRunner
from agents.watcher import WatcherHandler
from agents.tracer import TracerHandler
from agents.statistician import StatisticianHandler
from agents.briefer import BrieferHandler
from agents.librarian import LibrarianHandler

def main():
    print("=" * 70)
    print("  RIPPLE — All-in-One Autonomous System Launcher")
    print("  Starting 5 FalkorDB-coordinated workers + FastAPI Web Service")
    print("=" * 70)

    coord = CoordEngine(graph_manager.get_graph("coord"))
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))

    watcher_handler = WatcherHandler(knowledge, coord)
    tracer_handler = TracerHandler(knowledge, coord)
    stat_handler = StatisticianHandler(knowledge)
    briefer_handler = BrieferHandler(knowledge)

    def librarian_dispatch(payload):
        tenant = payload.get("tenant", "cardio")
        mem = TenantMemory(tenant)
        lib = LibrarianHandler(mem)
        return lib.consolidate()

    runners = [
        WorkerRunner("worker_watcher", "watcher", "ingest", watcher_handler.handle, coord=coord),
        WorkerRunner("worker_tracer", "tracer", "trace", tracer_handler.handle, coord=coord),
        WorkerRunner("worker_statistician", "statistician", "quantify", stat_handler.handle, coord=coord),
        WorkerRunner("worker_briefer", "briefer", "brief", briefer_handler.handle, coord=coord),
        WorkerRunner("worker_librarian", "librarian", "consolidate", librarian_dispatch, coord=coord),
    ]

    worker_threads = []
    print("\n[*] Registering and starting 5 background workers...")
    for r in runners:
        t = threading.Thread(target=r.start, daemon=True, name=r.agent_id)
        t.start()
        worker_threads.append(t)
        print(f"  ✓ Started {r.agent_id} ({r.role}) listening on task_type '{r.task_type}'")

    # Configure Uvicorn
    config = uvicorn.Config(
        app="api:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    stop_called = False

    def handle_shutdown(signum, frame):
        nonlocal stop_called
        if stop_called:
            return
        stop_called = True
        print("\n[!] Received interrupt signal. Initiating clean shutdown...")
        server.should_exit = True
        for r in runners:
            r.stop()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print(f"\n[*] Starting Uvicorn web server on http://{settings.api_host}:{settings.api_port}")
    print("[*] Press Ctrl+C at any time for clean graceful shutdown.\n")

    try:
        server.run()
    finally:
        print("[*] Stopping worker runners...")
        for r in runners:
            r.stop()
        for t in worker_threads:
            t.join(timeout=2.0)
        print("[✓] All services and workers stopped cleanly.")

if __name__ == "__main__":
    main()
