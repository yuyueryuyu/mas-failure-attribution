from enum import Enum
import json
from pathlib import Path
import shutil
from typing import Type

from adapter.base_adapter import BaseAdapter
from model.schema import History
from monitor.attack_monitor import AttackMonitor
from monitor.base_monitor import BaseMonitor, RoleType
from utils.common import dumps
from utils.logging import logger
from utils.prompts import REPLAY_PROMPT

class RunMode(Enum):
    NONE = 0
    ATTACK = 1
    DIAGNOSE = 2

def run_coding_task(
    task: dict,
    workspace: Path,
    output: Path,
    backend: BaseAdapter,
    recovery_dir: Path = None,
    skip_existing: bool = True,
    monitor: BaseMonitor = None,
    replay_info="",
):
    """
    Execute a coding task using a multi-agent backend system.
    Args:
        task (dict): Task specification. load from dataset
        workspace (Path): Working directory where the backend executes the task
        output (Path): Directory where logs and results are saved
        Backend (Type[BaseAdapter]): Backend adapter class for task execution
        recovery_dir (Path, optional): Path to recovery state for resuming former tasks. Defaults to None.
        skipping_exists (bool, optional): If True, skip execution if log already exists. Defaults to True.
        run_mode (RunMode, optional): Execution mode configuration. Defaults to RunMode.NONE.
    Returns:
        None
    """
    data_source = task["data_source"]
    task_id = task["task_id"]
    idea = (
        replay_info
        + task["question"]
        + f"I wish you finish the task with a multi-agent cooperation"
        + f"The file name of your solution MUST be 'solution.py' and MUST be located at root directory"
    )
    log = output / 'log.json'
    if log.exists():
        if skip_existing:
            logger.info(f'Log for task {task_id} exists, skipping this round...')
            return
        else:
            logger.info(f'Log for task {task_id} exists, overriding...')
            shutil.rmtree(workspace, ignore_errors=True)
            shutil.rmtree(output, ignore_errors=True)
            workspace.mkdir(parents=True, exist_ok=True)
            output.mkdir(parents=True, exist_ok=True)
    try:
        backend.run_backend(
            idea=idea,
            workspace=workspace,
            recovery=recovery_dir,
            monitor=monitor
        )
    except Exception as e:
        logger.error(f"Error running task {data_source}/{task_id}: {e}")
    
    logger.info(f'Task {data_source}/{task_id} ends executing...')
    solution_path = workspace / 'solution.py'
    if solution_path.exists():
        model_prediction = solution_path.read_text()
    else:
        model_prediction = ""
        logger.warning(f'solution.py not found for task {data_source}/{task_id}')
    
    prompt_map = backend.get_prompt_map()

    used_roles = set(h.name for h in monitor.history)
    system_prompts = {
        name: prompt_map[name]
        for name in used_roles
    }

    if monitor.should_inject():
        return False

    with open(log, "w", encoding="utf-8") as f:
        json.dump(
            {
                "question": task["question"],
                "question_ID": task["task_id"],
                "ground_truth": task["reference_solution"],
                "test": task["test"],
                "model_prediction": model_prediction,
                "history": dumps(monitor.history),
                "topology": dumps(monitor.topology),
                "system_prompts": system_prompts,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return True

def replay_coding_task(
    task: dict,
    workspace: Path,
    output: Path,
    backend: BaseAdapter,
    replay_info: list,
    recovery_dir: Path = None,
    skip_existing: bool = True,
):
    recovery_path = output / 'recovery'
    logger.info('recovery info detected, resuming monitor...')
    monitor = AttackMonitor.deserialize(recovery_dir, recovery_path, workspace, backend, replay_info[-1])
    # MOVE last round's workspace to current round's workspace
    shutil.copytree(
        recovery_dir / 'workspace', 
        workspace,
        dirs_exist_ok=True
    )
    return run_coding_task(
        task,
        workspace,
        output,
        backend,
        skip_existing=skip_existing,
        monitor=monitor,
        replay_info=REPLAY_PROMPT.format(original_task=task['question'], replay_info=replay_info)
    )