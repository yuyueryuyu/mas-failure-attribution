import argparse
import asyncio
from enum import Enum
import importlib
import json
import shutil
from typing import Type
import datasets

from adapter.base_adapter import BaseAdapter
from monitor.base_monitor import BaseMonitor
from utils.logging import handler
from utils.logging import logger
from utils.common import dumps
from pathlib import Path

def _load_backend(name: str) -> Type[BaseAdapter]:
    """Load backend module and validate required interface."""
    backend = importlib.import_module(f"adapter.{name}.core")
    return getattr(backend, f'{name}Adapter')

class RunMode(Enum):
    NONE = 0
    ATTACK = 1
    DIAGNOSE = 2

def run_coding_task(
    task: dict,
    workspace: Path,
    output: Path,
    Backend: Type[BaseAdapter],
    recovery_dir: Path = None,
    skipping_exists: bool = True,
    run_mode: RunMode = RunMode.NONE
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
        task["question"]
        + f"I wish you finish the task with a multi-agent cooperation"
        + f"The file name of your solution MUST be 'solution.py' and MUST be located at root directory"
    )
    log = output / 'log.json'
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
    # set recovery info saving path for this turn
    recovery_path = output / 'recovery'
    adapter = Backend()
    if not recovery_dir:
        logger.info('No recovery info, initializing new monitor...')
        monitor = BaseMonitor(recovery_path, workspace, adapter)
    else:
        logger.info('recovery info detected, resuming monitor...')
        monitor = BaseMonitor.deserialize(recovery_dir, recovery_path, workspace, adapter)
    try:
        adapter.run_backend(
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
    
    prompt_map = adapter.get_prompt_map()

    used_roles = set(h.name for h in monitor.history)
    system_prompts = {
        name: prompt_map[name]
        for name in used_roles
    }

    with open(log, "w", encoding="utf-8") as f:
        json.dump(
            {
                "question": task["question"],
                "question_ID": task["task_id"],
                "ground_truth": task["reference_solution"],
                "model_prediction": model_prediction,
                "history": dumps(monitor.history),
                "topology": dumps(monitor.topology),
                "system_prompts": system_prompts,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def main(args):
    dataset = datasets.load_dataset(
        "parquet", data_files={"train": args.dataset}, split="train"
    )
    logger.info(f"Loaded {len(dataset)} tasks from {args.dataset}")
    tasks = dataset.to_list()
    if args.max_samples is not None:
        tasks = tasks[: args.max_samples]
        logger.info(f"Using {len(tasks)} tasks (max_samples={args.max_samples})")
    backend = _load_backend(args.backend)
    data_source = tasks[0]["data_source"]
    current_round = 0
    base_workspace: Path = args.workspace
    base_output: Path = args.output
    # covert to absolute path 
    if not base_workspace.is_absolute():
        base_workspace = base_workspace.absolute()
    if not base_output.is_absolute():
        base_output = base_output.absolute()

    # ROUND 0: run without injecting / diagnosing
    for task in tasks:
        task_id = task["task_id"].replace("/", "_")
        workspace = base_workspace / data_source / f"round_{current_round}" / task_id
        output = base_output / data_source / f"round_{current_round}" / task_id
        workspace.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        run_coding_task(
            task,
            workspace,
            output,
            backend,
            skipping_exists=args.skip_existing
        )

    # TODO: eval ROUND 0

    # TODO: ROUND i >= 1: divide eval results of round 0 into success / fail
    # sucess -> attack pipeline
    # fail -> diagnose pipeline
    # current implementation is for testing replay function
    current_round += 1
    for i in range(current_round, args.max_rounds + 1):
        for task in tasks:
            task_id = task["task_id"].replace("/", "_")
            last_round_output = base_output / data_source / f"round_{current_round-1}" / task_id
            if not last_round_output.exists():
                raise FileNotFoundError(f'last round output not exists for {task_id}')
            workspace = base_workspace / data_source / f"round_{current_round}" / task_id
            output = base_output / data_source / f"round_{current_round}" / task_id
            workspace.mkdir(parents=True, exist_ok=True)
            output.mkdir(parents=True, exist_ok=True)
            replay_step = 5
            recovery_dir = last_round_output / 'recovery' / f'step_{replay_step}'
            # MOVE last round's workspace to current round's workspace
            shutil.copytree(
                recovery_dir / 'workspace', 
                workspace,
                dirs_exist_ok=True
            )
            run_coding_task(
                task,
                workspace,
                output,
                backend,
                recovery_dir=recovery_dir,
                skipping_exists=args.skip_existing
            )
    
if __name__ == "__main__":
    handler.doRollover()
    parser = argparse.ArgumentParser(description="Universal attack and diagnosis framework")
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Dataset path",
    )
    parser.add_argument(
        "--backend",
        type=str,
        required=True,
        help="MAS backend name",
    )
    parser.add_argument("--workspace", type=Path, required=True, help="Working directory path")
    parser.add_argument("--output", type=Path, required=True, help="Output directory path")
    parser.add_argument("--max_rounds", type=int, default=3, help="Maximum number of rounds")
    parser.add_argument("--max_samples", type=int, default=None, help="Maximum number of samples")
    
    # TODO: concurrency
    parser.add_argument("--concurrent", action="store_true", help="Enable concurrent processing")
    parser.add_argument("--skip_existing", "-s", action="store_true")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["full", "attack", "diagnose"],
        default="full",
        help="Run mode",
    )

    # Retry related parameters
    parser.add_argument(
        "--max_retries",
        type=int,
        default=3,
        help="Maximum retry count (default: 3)",
    )
    parser.add_argument(
        "--retry_delay",
        type=int,
        default=2,
        help="Retry interval in seconds (default: 2)",
    )
    parser.add_argument(
        "--backoff_factor",
        type=float,
        default=1.5,
        help="Backoff factor (default: 1.5)",
    )

    args = parser.parse_args()
    main(args)