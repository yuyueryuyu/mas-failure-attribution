import asyncio
import base64
import json
import os
from pathlib import Path
import shutil
import tqdm

from utils.common import read_json_file
from utils.logging import logger
from sandbox_fusion import (
    RunCodeRequest,
    RunStatus,
    run_code,
)

def code_exec(code: str, test: str):

    base64_content = base64.b64encode(code.encode("utf-8")).decode("utf-8")
    request = RunCodeRequest(
        language="pytest",
        code=test,
        files={"solution.py": base64_content},
    )
    try:
        return run_code(request, client_timeout=60)
    except Exception as e:
        # Log exception details
        logger.error(f"Error in code_exec_async: {e}", exc_info=True)
        # Depending on needs, you can return a custom error object or None
        print(f"Error in code_exec_async: {e}")
        return None

def run_correctness_eval_task(
    task: dict
) -> tuple[str, bool]:
    solution = task["model_prediction"]
    test = task["test"]
    result = code_exec(solution, test)
    return task["question_ID"], result.status == RunStatus.Success


def run_eval_tasks(
    eval_path: Path,
    data_source: str,
    skip_existing: bool = True,
) -> dict[str, bool]:
    """
    Input:
        tasks: list[dict]
    Output:
        dict[str, bool]: {task_id: pass/fail}
    """
    logger.info(f'Starting to eval tasks in {eval_path}...')
    filename = f"eval_{data_source}.json"
    save_path = eval_path / filename
    if save_path.exists():
        if skip_existing:
            logger.info(f'Eval result for {data_source} exists, skipping...')
            return
        else:
            logger.info(f'Eval result for {data_source} exists, overriding...')

    eval_log_paths = [p / 'log.json' for p in eval_path.iterdir() if p.is_dir()]
    tasks = [read_json_file(p) for p in eval_log_paths if p.exists()]
    results = [run_correctness_eval_task(task) for task in tasks]
    results = {task_id: result for task_id, result in results}

    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "w") as f:
        json.dump(results, f)
        logger.info(f'Ending to eval tasks in {eval_path}, results saved in {save_path}...')

def load_eval_results(
    eval_path: Path,
    data_source: str,
):
    eval_results = read_json_file(eval_path / f"eval_{data_source}.json")
    return eval_results
    