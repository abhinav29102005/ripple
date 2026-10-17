"""
Generic worker runner loop for Ripple agents.
Handles registration, lease heartbeats, graceful shutdown,
and self-healing lease reclamation.
"""
import time
import threading
import signal
import sys
from typing import Any, Callable, Dict, Optional
from coord import CoordEngine

class WorkerRunner:
    def __init__(
        self,
        agent_id: str,
        role: str,
        task_type: Optional[str] = None,
        handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        lease_duration: int = 30,
        poll_interval: float = 0.5,
        reclaim_interval: float = 5.0,
        coord: Optional[CoordEngine] = None,
    ):
        self.agent_id = agent_id
        self.role = role
        self.task_type = task_type
        self.handler = handler or (lambda p: {"status": "ok", "echo": p})
        self.lease_duration = lease_duration
        self.poll_interval = poll_interval
        self.reclaim_interval = reclaim_interval
        self.coord = coord or CoordEngine()
        self._running = False
        self._last_reclaim = 0.0

    def start(self) -> None:
        self._running = True
        self.coord.register_agent(self.agent_id, self.role)

        # Handle signals if in main thread
        try:
            signal.signal(signal.SIGINT, self._handle_exit)
            signal.signal(signal.SIGTERM, self._handle_exit)
        except (ValueError, AttributeError):
            pass

        self._loop()

    def stop(self) -> None:
        self._running = False

    def _handle_exit(self, signum, frame):
        self.stop()

    def _loop(self) -> None:
        while self._running:
            now = time.time()
            if now - self._last_reclaim >= self.reclaim_interval:
                try:
                    self.coord.reclaim_expired_leases()
                    self.coord.agent_heartbeat(self.agent_id)
                except Exception:
                    pass
                self._last_reclaim = now

            task = None
            try:
                task = self.coord.claim_task(
                    agent_id=self.agent_id,
                    task_type=self.task_type,
                    lease_seconds=self.lease_duration,
                )
            except Exception:
                time.sleep(self.poll_interval)
                continue

            if not task:
                time.sleep(self.poll_interval)
                continue

            self._process_task(task)

    def _process_task(self, task: Dict[str, Any]) -> None:
        task_id = task["id"]
        stop_heartbeat = threading.Event()

        def heartbeat_worker():
            interval = max(2.0, self.lease_duration / 3.0)
            while not stop_heartbeat.wait(interval):
                try:
                    self.coord.heartbeat_task(task_id, self.agent_id, self.lease_duration)
                    self.coord.agent_heartbeat(self.agent_id)
                except Exception:
                    pass

        hb_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        hb_thread.start()

        try:
            result = self.handler(task["payload"])
            self.coord.complete_task(task_id, self.agent_id, result if isinstance(result, dict) else {"result": result})
        except Exception as e:
            self.coord.fail_task(task_id, self.agent_id, str(e))
        finally:
            stop_heartbeat.set()
            hb_thread.join(timeout=2.0)
