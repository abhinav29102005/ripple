"""
FalkorDB connection and graph management for Ripple.
Provides single-source connection pooling and graph initialization.
"""
from typing import Any, Dict, List, Optional
from falkordb import FalkorDB, Graph
from config import settings

class GraphManager:
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        self.host = host or settings.falkordb_host
        self.port = port or settings.falkordb_port
        self._db: Optional[FalkorDB] = None

    @property
    def db(self) -> FalkorDB:
        if self._db is None:
            self._db = FalkorDB(host=self.host, port=self.port)
        return self._db

    def get_graph(self, name: str) -> Graph:
        """Select a named graph (coord, knowledge, tenant_<id>)."""
        return self.db.select_graph(name)

    def delete_graph(self, name: str) -> bool:
        """Safely delete a graph if it exists."""
        try:
            g = self.get_graph(name)
            g.delete()
            return True
        except Exception:
            return False

    def list_graphs(self) -> List[str]:
        """List all existing graphs in FalkorDB."""
        try:
            res = self.db.connection.execute_command("GRAPH.LIST")
            if isinstance(res, list):
                return [g.decode() if isinstance(g, bytes) else str(g) for g in res]
            return []
        except Exception:
            return []

    def init_coord_schema(self) -> Graph:
        """Initialize indexes for the coord graph."""
        g = self.get_graph("coord")
        indexes = [
            ("Task", "id"),
            ("Task", "status"),
            ("Task", "type"),
            ("Task", "key"),
            ("Agent", "id"),
        ]
        for label, prop in indexes:
            try:
                g.query(f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
            except Exception:
                pass
        return g

    def init_knowledge_schema(self) -> Graph:
        """Initialize indexes for the knowledge graph."""
        g = self.get_graph("knowledge")
        indexes = [
            ("Trial", "id"),
            ("Review", "id"),
            ("Guideline", "id"),
            ("Retraction", "id"),
            ("Impact", "id"),
            ("Person", "id"),
            ("Committee", "id"),
            ("Decision", "id"),
            ("Document", "id"),
            ("Ticket", "id"),
            ("Message", "id"),
            ("Topic", "name"),
        ]
        for label, prop in indexes:
            try:
                g.query(f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
            except Exception:
                pass
        return g

    def init_tenant_schema(self, tenant_id: str) -> Graph:
        """Initialize indexes for a tenant memory graph."""
        g = self.get_graph(f"tenant_{tenant_id}")
        indexes = [
            ("Session", "id"),
            ("Message", "id"),
            ("Episode", "id"),
            ("Rule", "id"),
            ("Fact", "id"),
            ("Ranking", "id"),
        ]
        for label, prop in indexes:
            try:
                g.query(f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
            except Exception:
                pass
        return g

    def save_state(self) -> None:
        """Trigger background or sync snapshot save in FalkorDB / Redis."""
        try:
            self.db.connection.execute_command("BGSAVE")
        except Exception:
            try:
                self.db.connection.execute_command("SAVE")
            except Exception:
                pass

# Global singleton manager
graph_manager = GraphManager()
