"""Injection-aware monitor used during replay and attribution rounds."""

from pathlib import Path
from typing import Any

from pydantic import PrivateAttr

from adapter.base_adapter import BaseAdapter
from monitor.base_monitor import BaseMonitor
from utils.common import read_json_file


class AttackMonitor(BaseMonitor):
    """Monitor variant that injects a single planned replay modification."""

    _attack_step: int = PrivateAttr()
    _attack_suggestion: str = PrivateAttr()

    def __init__(self, recovery: Path, workspace:Path, backend: BaseAdapter, suggestion: dict, **data: Any):
        """Initialize attack monitor from suggestion payload and base metadata."""
        super().__init__(recovery, workspace, backend, **data)
        self._attack_step = suggestion['step_id']
        if 'attacked_content' in suggestion:
            self._attack_suggestion = suggestion['attacked_content']
        elif 'suggested_fix' in suggestion:
            self._attack_suggestion = suggestion['suggested_fix']
        else:
            raise KeyError('not found key in suggestion')

    @classmethod
    def deserialize(
        cls, 
        stg_path: Path, 
        recovery: Path, 
        workspace: Path, 
        backend: BaseAdapter,
        suggestion: dict,
    ) -> "AttackMonitor":
        """Deserialize monitor state and bind the current injection suggestion."""
        monitor_info_path = stg_path.joinpath("monitor.json")
        if not monitor_info_path.exists():
            raise FileNotFoundError(
                "recover storage meta file `team.json` not exist, " "not to recover and please start a new project."
            )

        monitor_info: dict = read_json_file(monitor_info_path)
        monitor = AttackMonitor(
            recovery=recovery, 
            workspace=workspace, 
            backend=backend, 
            suggestion=suggestion,
            **monitor_info
        )
        return monitor

    def should_inject(self):
        """Return True when current step matches configured injection step."""
        return self.step == self._attack_step
    
    def get_injection_content(self):
        """Return injected content for current attack/diagnosis replay step."""
        return self._attack_suggestion