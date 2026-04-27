from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict


class BaseAdapter(ABC):
    @abstractmethod
    def run_backend(
        self,
        idea: str,
        workspace: Path,
        recovery: Path = None,
        monitor = None,
        enable_lint: bool = True,
    ):
        pass

    @abstractmethod
    def save_current_state(
        self,
        path: Path
    ):
        pass

    @abstractmethod
    def get_prompt_map(self) -> Dict[str, str]:
        pass