from enum import Enum
from pathlib import Path
import shutil
from typing import Any, Callable

from pydantic import BaseModel, Field, PrivateAttr
from adapter.base_adapter import BaseAdapter
from model.schema import Topology, History
from utils.logging import logger
from utils.common import read_json_file, write_json_file

class RoleType(Enum):
    TERMINAL = "Terminal"
    ASSISTANT = "Assistant"

class BaseMonitor(BaseModel):
    history: list[History] = Field(default=[])
    topology: Topology = Field(default=Topology())
    step: int = Field(default=1)

    _recovery: Path = PrivateAttr()
    _workspace: Path = PrivateAttr()
    _backend: BaseAdapter = PrivateAttr()

    def __init__(self, recovery: Path, workspace: Path, backend: BaseAdapter, **data: Any):
        super().__init__(**data)
        self._recovery = recovery
        self._workspace = workspace
        self._backend = backend

    def serialize(self, stg_path: Path = None):
        monitor_info_path = stg_path.joinpath("monitor.json")
        serialized_data = self.model_dump()
        write_json_file(monitor_info_path, serialized_data)
    
    @classmethod
    def deserialize(cls, stg_path: Path, recovery: Path, workspace: Path, backend: BaseAdapter) -> "BaseMonitor":
        monitor_info_path = stg_path.joinpath("monitor.json")
        if not monitor_info_path.exists():
            raise FileNotFoundError(
                "recover storage meta file `team.json` not exist, " "not to recover and please start a new project."
            )

        monitor_info: dict = read_json_file(monitor_info_path)
        monitor = BaseMonitor(
            recovery=recovery, 
            workspace=workspace, 
            backend=backend, 
            **monitor_info
        )
        return monitor

    def record_step(self, content: str, name: str, role: RoleType):
        if role == RoleType.TERMINAL:
            # Merge terminal output into the previous step. 
            assert len(self.history) > 0, f'terminal outputs while no previous step'
            last_step = self.history[-1]
            last_step.content += f"\n\n{content}"
            logger.info(
                f"Terminal output merged into previous step"
            )
            return
        
        # Record normal step
        recovery_step = self._recovery / f'step_{self.step}'
        recovery_step.mkdir(parents=True, exist_ok=True)
        self._backend.save_current_state(recovery_step)
        self.serialize(recovery_step)
        shutil.copytree(self._workspace, recovery_step / 'workspace')
        self.history.append(
            History(
                step=self.step,
                content=content,
                role=role.value,
                name=name
            )
        )
        self.step += 1

    def record_topology(self, src: str, dst: str):
        self.topology.add_edge(src, dst)
        