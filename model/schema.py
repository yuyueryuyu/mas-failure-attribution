from pydantic import BaseModel, Field

class Topology(BaseModel):
    nodes: list[str] = Field(default=[])
    adjacency_list: dict[str, list[str]] = Field(default={})

    def add_node(self, node: str):
        if node not in self.nodes:
            self.nodes.append(node)
    
    def add_edge(self, src: str, dst: str):
        self.add_node(src)
        self.add_node(dst)
        adj = self.adjacency_list.setdefault(src, [])
        if dst not in adj:
            adj.append(dst)

class History(BaseModel):
    step: int = Field(default=0)
    content: str = Field(default="")
    role: str = Field(default="")
    name: str = Field(default="")