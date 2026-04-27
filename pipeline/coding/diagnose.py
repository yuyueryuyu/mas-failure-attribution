import json
from pathlib import Path
import shutil
from typing import Type

from adapter.base_adapter import BaseAdapter
from utils.common import read_json_file, write_json_file
from utils.fault_library import fault_candidates_for_prompt
from utils.prompts import DIAGNOSE_ANALYSIS_PROMPT
from utils.logging import logger

def diagnose_analysis(
    task: dict,
    workspace: Path,
    output: Path,
    backend: BaseAdapter,
    injection_history: list[dict] = [],
    skipping_exists: bool = True,
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
    task_id = task["question_ID"]
    logger.info(f'Diagnose Analysis start for Task ID: {task_id}, workspace: {workspace}, output: {output}')
    if len(injection_history) > 0:
        min_step_id = injection_history[-1]['step_id']
    else:
        min_step_id = 0
    idea = DIAGNOSE_ANALYSIS_PROMPT.format(
        task_id=task["question_ID"],
        question=task["question"],
        ground_truth=task["ground_truth"],
        model_prediction=task["model_prediction"],
        fault_pool_json=fault_candidates_for_prompt(),
        topology_info=task['topology'],
        history_str=task['history'],
        injection_history=injection_history,
        min_step_id=min_step_id,
    )
    log = output / 'diagnose_analysis.json'
    if log.exists():
        if skipping_exists:
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
            enable_lint=False,
        )
    except Exception as e:
        logger.error(f"Error running task {task_id}: {e}")
        return False
    
    logger.info(f'Task {task_id} ends executing...')
    result_path = workspace / f'{task_id}_diagnose_analysis.json'
    if result_path.exists():
        try:
            diagnose_suggestion = read_json_file(result_path)
        except:
            logger.error(f'attack analysis result read errors for task {task_id}')
            return False
    else:
        logger.error(f'diagnose analysis result not found for task {task_id}')
        return False

    write_json_file(
        log,
        injection_history + [diagnose_suggestion]
    )
    return True

def get_diagnose_analysis(
    output: Path
) -> list[dict]:
    return read_json_file(output / 'diagnose_analysis.json')