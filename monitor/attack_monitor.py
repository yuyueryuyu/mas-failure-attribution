from pathlib import Path

from monitor.base_monitor import BaseMonitor


class AttackMonitor(BaseMonitor):
    def __init__(self, recovery: Path, workspace:Path, attack_suggestions: list):
        super().__init__(recovery, workspace)
        self.attack_suggestions = attack_suggestions