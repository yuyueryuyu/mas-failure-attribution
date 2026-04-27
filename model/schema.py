"""Pydantic schemas for interaction topology and execution history records."""

from pydantic import BaseModel, Field

class Topology(BaseModel):
    """Store directed collaboration graph among roles."""

    nodes: list[str] = Field(default=[])
    adjacency_list: dict[str, list[str]] = Field(default={})

    def add_node(self, node: str):
        """Add a node if it does not exist in the topology."""
        if node not in self.nodes:
            self.nodes.append(node)
    
    def add_edge(self, src: str, dst: str):
        """Add a directed edge from source role to destination role."""
        self.add_node(src)
        self.add_node(dst)
        adj = self.adjacency_list.setdefault(src, [])
        if dst not in adj:
            adj.append(dst)

class History(BaseModel):
    """Represent one recorded execution step from a role."""

    step: int = Field(default=0)
    content: str = Field(default="")
    role: str = Field(default="")
    name: str = Field(default="")