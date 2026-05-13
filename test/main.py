"""Entry point for running iterative attack/diagnosis attribution workflows.

This module orchestrates:
- task loading from a parquet dataset,
- round-based coding task execution,
- evaluation-driven branching into attack or diagnosis analysis,
- replay from recovery snapshots,
- and final attribution result persistence.
"""

# Standard library imports.
import argparse
import importlib
import shutil
from pathlib import Path
from typing import Type

# Third-party library imports.
import datasets
from sandbox_fusion import set_dataset_endpoint, set_sandbox_endpoint

# Project-local imports: adapters and monitors.
from adapter.base_adapter import BaseAdapter
from monitor.attack_monitor import AttackMonitor
from monitor.base_monitor import BaseMonitor

# Project-local imports: pipeline stages.
from pipeline.coding.attack import attack_analysis, get_attack_analysis
from pipeline.coding.diagnose import diagnose_analysis, get_diagnose_analysis
from pipeline.coding.eval import load_eval_results, run_eval_tasks
from pipeline.coding.run import run_coding_task
from pipeline.multimodal_task.multimodal_eval import load_eval_results_new, run_eval_tasks_new

# Project-local imports: utilities.
from utils.common import match_info, read_json_file, save_final_result
from utils.task_record import normalize_parquet_task_row
from utils.logging import handler
from utils.logging import logger
from adapter.MagenticOne.magentic_runtime import _load_config_from_ini

def _load_backend(name: str) -> Type[BaseAdapter]:
    """Load a backend adapter class by backend name.

    Args:
        name: Backend identifier that maps to ``adapter.<name>.core``.

    Returns:
        A class object that implements the ``BaseAdapter`` interface.
    """
    backend = importlib.import_module(f"adapter.{name}.core")
    return getattr(backend, f'{name}Adapter')


def main(args):
    """Run the full multi-round attribution pipeline.

    The function performs round-0 execution, evaluates outcomes, and then
    iteratively applies attack or diagnosis analysis based on previous-round
    evaluation results. It replays tasks from recovery snapshots and persists
    final attribution records when behavior flips between rounds.

    Args:
        args: Parsed CLI arguments used to configure dataset, backend,
            workspace/output directories, and round execution controls.
    """
    dataset = datasets.load_dataset(
        "parquet", data_files={"train": args.dataset}, split="train"
    )
    logger.info(f"Loaded {len(dataset)} tasks from {args.dataset}")
    tasks = dataset.to_list()
    if args.max_samples is not None:
        tasks = tasks[: args.max_samples]
        logger.info(f"Using {len(tasks)} tasks (max_samples={args.max_samples})")
    tasks = [
        normalize_parquet_task_row(t, dataset_path=args.dataset)
        for t in tasks
    ]
    Backend = _load_backend(args.backend)
    backend = Backend()

    data_source = (tasks[0].get("data_source") or "").strip() if tasks else ""
    if not data_source:
        data_source = Path(str(args.dataset)).stem
    workspace_root: Path = args.workspace
    output_root: Path = args.output

    skip_existing = args.skip_existing
    max_rounds = args.max_rounds
    rollout_only = args.rollout

    # covert to absolute path 
    if not workspace_root.is_absolute():
        workspace_root = workspace_root.absolute()
    if not output_root.is_absolute():
        output_root = output_root.absolute()

    # ROUND 0: run without injecting / diagnosing
    for task in tasks:
        task_id = task["task_id"].replace("/", "_")
        workspace = workspace_root / data_source / f"round_0" / task_id
        output = output_root / data_source / f"round_0" / task_id
        workspace.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)

        logger.info('No recovery info, initializing new monitor...')
        recovery_path = output / 'recovery'
        monitor = BaseMonitor(recovery_path, workspace, backend)
        
        run_coding_task(
            task,
            workspace,
            output,
            backend,
            skip_existing=skip_existing,
            monitor=monitor
        )

    # Start to eval round 0
    eval_path = output_root / data_source / "round_0"
    if args.backend == "MagenticOne":
        run_eval_tasks_new(eval_path, data_source=data_source, skip_existing=skip_existing)
        eval_results = load_eval_results_new(eval_path, data_source)
    else:
        run_eval_tasks(eval_path, data_source=data_source, skip_existing=skip_existing)
        eval_results = load_eval_results(eval_path, data_source)
    
    if rollout_only:
        logger.info(
            "rollout=True: stop after round-0 eval (only e.g. round_0/.../log.json). "
            "attack_analysis / diagnose_analysis and args.mode are not used. "
            "Set rollout=False to run round>=1 strategist + AttackMonitor replay."
        )
        return

    # From here: round >= 1 (strategist + executor). This block is skipped entirely when rollout=True above.
    # Pipeline roles (round >= 1):
    # - attack_analysis / diagnose_analysis: strategist (JSON plan: step_id, content, …).
    # - AttackMonitor + run_coding_task: executor — replay with REPLAY_PROMPT injection
    #   (MetaGPT: ThinkMiddleware on aask; MagenticOne: MagenticReplayMiddleware on create/create_stream in core).
    # args.mode: full = success→attack, fail→diagnose; attack = only attack branch on success;
    # diagnose = only diagnose branch on failure (other branch copies prior round without strategist).
    mode = getattr(args, "mode", "full")
    logger.info("Round>=1 pipeline mode=%s (strategist=attack|diagnose analysis, executor=AttackMonitor replay)", mode)
    completed_tasks = []
    for current in range(1, max_rounds + 1):
        for task in tasks:        
            task_id = task["task_id"].replace("/", "_")
            if task_id in completed_tasks:
                continue
            
            logger.info(f'Round {current}: Start to process Task {task_id}')
            last_round_output = output_root / data_source / f"round_{current-1}" / task_id
            if not last_round_output.exists():
                raise FileNotFoundError(f'last round output not exists for {task_id}')

            last_round_log = read_json_file(last_round_output / 'log.json') 
            output = output_root / data_source / f"round_{current}" / task_id
            output.mkdir(parents=True, exist_ok=True)

            if eval_results[task_id]:
                # attack branch
                logger.info(f'Last round processed as success for {task_id}, start the attack process...')
                
                workspace = workspace_root / data_source / f"round_{current}" / f'{task_id}_attack_analysis'
                workspace.mkdir(parents=True, exist_ok=True)
                previous_injections_path = last_round_output / 'attack_analysis.json'
                previous_injections = (
                    read_json_file(previous_injections_path) 
                        if previous_injections_path.exists() else []
                )

                is_success = attack_analysis(
                    task=last_round_log,
                    workspace=workspace,
                    output=output,
                    backend=backend,
                    skipping_exists=skip_existing,
                    injection_history=previous_injections
                )

                if not is_success:
                    logger.info(f'Attack Analysis Failed, skipping this round...')
                    shutil.copytree(
                        last_round_output,
                        output,
                        dirs_exist_ok=True
                    )
                    continue

                replay_info = get_attack_analysis(output)
            else:
                # diagnose
                logger.info(f'Last round processed as failure for {task_id}, start the diagnosis process...')
                
                workspace = workspace_root / data_source / f"round_{current}" / f'{task_id}_diagnose_analysis'
                workspace.mkdir(parents=True, exist_ok=True)

                previous_injections_path = last_round_output / 'diagnose_analysis.json'
                previous_injections = (
                    read_json_file(previous_injections_path) 
                        if previous_injections_path.exists() else []
                )

                is_success = diagnose_analysis(
                    task=last_round_log,
                    workspace=workspace,
                    output=output,
                    backend=backend,
                    skipping_exists=skip_existing,
                    injection_history=previous_injections
                )
                if not is_success:
                    logger.info(f'Diagnose Analysis Failed, skipping this round...')
                    shutil.copytree(
                        last_round_output,
                        output,
                        dirs_exist_ok=True
                    )
                    continue
                replay_info = get_diagnose_analysis(output)
            
            monitor = AttackMonitor(recovery_path, workspace, backend, replay_info[-1], last_round_log)
            result = run_coding_task(
                task,
                workspace,
                output,
                backend,
                skip_existing=skip_existing,
                monitor=monitor
            )
            if not result:
                logger.info(f'Replay Failed, skipping this round...')
                shutil.copytree(
                    last_round_output,
                    output,
                    dirs_exist_ok=True
                )
                continue

        # save last round's eval results
        last_eval_results = eval_results
        eval_path = output_root / data_source / f"round_{current}"
        
        # Check if round_{current} directory has any task outputs before evaluating
        if not eval_path.exists() or not any(p.is_dir() for p in eval_path.iterdir()):
            logger.warning(f"No task outputs found in {eval_path}, skipping evaluation for round {current}")
            continue
        
        if args.backend == "MagenticOne":
            run_eval_tasks_new(eval_path, data_source=data_source, skip_existing=skip_existing)
            eval_results = load_eval_results_new(eval_path, data_source)
        else:
            run_eval_tasks(eval_path, data_source=data_source, skip_existing=skip_existing)
            eval_results = load_eval_results(eval_path, data_source)
        
        for task_id in eval_results:
            if eval_results[task_id] ^ last_eval_results[task_id]:
                output = output_root / data_source / f"round_{current}" / task_id
                if last_eval_results[task_id]:
                    logger.info(f'[Round {current}] Attack result eval changed to failure, diagnosing...')
                    last_round_output = output_root / data_source / f"round_{current}" / task_id
                    if not last_round_output.exists():
                        raise FileNotFoundError(f'last round output not exists for {task_id}')
                    last_round_log = read_json_file(last_round_output / 'log.json') 
                    workspace = workspace_root / data_source / f"round_{current}" / f'{task_id}_diagnose_analysis'
                    workspace.mkdir(parents=True, exist_ok=True)
                    is_success = diagnose_analysis(
                        task=last_round_log,
                        workspace=workspace,
                        output=output,
                        backend=backend,
                        skipping_exists=skip_existing,
                    )
                    final_info = get_attack_analysis(output)
                    if is_success:
                        diagnose_info = get_diagnose_analysis(output)
                        if match_info(final_info, diagnose_info):
                           logger.info(f'Direct diagnose success, regarding as easy injection...')
                           continue 
                else:
                    last_round_output = output_root / data_source / f"round_{current-1}" / task_id
                    if not last_round_output.exists():
                        raise FileNotFoundError(f'last round output not exists for {task_id}')
                    last_round_log = read_json_file(last_round_output / 'log.json') 
                    final_info = get_diagnose_analysis(output)

                completed_tasks.append(task_id)
                save_final_result(output_root / 'final_results', last_round_log, final_info)
            else:
                logger.info(f'Eval Result remains the same, Attack/Diagnose Fail...')
        
if __name__ == "__main__":
    # Load config.ini into environment variables first.
    _load_config_from_ini()
    handler.doRollover()
    set_sandbox_endpoint("http://localhost:8080/")
    set_dataset_endpoint("http://localhost:8080/online_judge/")
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
    parser.add_argument("--rollout", action="store_true", help="Stop after round 0 + eval only; no attack/diagnose (--mode ignored).")
    # TODO: add mode to control the run mode
    parser.add_argument(
        "--mode",
        type=str,
        choices=["full", "attack", "diagnose"],
        default="full",
        help=(
            "Only used when rollout is False (round>=1). full=success→attack+replay, fail→diagnose+replay; "
            "attack=only attack path on eval success; diagnose=only diagnose path on eval failure."
        ),
    )

    # args = parser.parse_args()
    # Debug: fake argv (no script name), equivalent to CLI. Example:
    # --- kodcode debug (keep; uncomment whole block when needed) ---
    # args = argparse.Namespace(
    #     dataset=r"D:\myproject\mira-ai-lab\mas-failure-attribution\adapter\MagenticOne\dataset\code\kodcode-light-rl-10k-hard.parquet",
    #     backend="MagenticOne",
    #     workspace=Path(r"D:\myproject\mira-ai-lab\mas-failure-attribution\runs\magentic_workspace"),
    #     output=Path(r"D:\myproject\mira-ai-lab\mas-failure-attribution\runs\magentic_output"),
    #     max_samples=1,
    #     rollout=True,
    #     skip_existing=False,
    #     max_rounds=3,
    #     concurrent=False,
    #     mode="full",
    # )
    _GAIA_VAL = r"D:\myproject\mira-ai-lab\mas-failure-attribution\dataset\gaia_dataset_raw\2023\validation"
    # GAIA presets below use rollout=True → main() returns after round_0 eval; you only get
    # round_0/.../log.json. mode="full" does NOT control that; set rollout=False to run attack/diagnose.
    # --- GAIA metadata.level1 (default local run; switch level by changing which `args =` line is active) ---
    _args_gaia_level1 = argparse.Namespace(
        dataset=rf"{_GAIA_VAL}\metadata.level1.parquet",
        backend="MagenticOne",
        workspace=Path(r"D:\myproject\mira-ai-lab\mas-failure-attribution\runs\magentic_workspace"),
        output=Path(r"D:\myproject\mira-ai-lab\mas-failure-attribution\runs\magentic_output"),
        max_samples=10,
        rollout=True,
        skip_existing=False,
        max_rounds=3,
        concurrent=False,
        mode="full",
    )
    _args_gaia_level2 = argparse.Namespace(
        dataset=rf"{_GAIA_VAL}\metadata.level2.parquet",
        backend="MagenticOne",
        workspace=Path(r"D:\myproject\mira-ai-lab\mas-failure-attribution\runs\magentic_workspace"),
        output=Path(r"D:\myproject\mira-ai-lab\mas-failure-attribution\runs\magentic_output"),
        max_samples=1,
        rollout=True,
        skip_existing=False,
        max_rounds=3,
        concurrent=False,
        mode="full",
    )
    _args_gaia_level3 = argparse.Namespace(
        dataset=rf"{_GAIA_VAL}\metadata.level3.parquet",
        backend="MagenticOne",
        workspace=Path(r"D:\myproject\mira-ai-lab\mas-failure-attribution\runs\magentic_workspace"),
        output=Path(r"D:\myproject\mira-ai-lab\mas-failure-attribution\runs\magentic_output"),
        max_samples=5,
        rollout=True,
        skip_existing=False,
        max_rounds=3,
        concurrent=False,
        mode="full",
    )
    # MagenticOne pipeline smoke: rollout=False so round>=1 runs strategist (attack/diagnose) + executor
    # (AttackMonitor; replay injection wired in adapter.MagenticOne.core). Toggle mode: full | attack | diagnose.
    _args_magentic_one_pipeline = argparse.Namespace(
        dataset=rf"{_GAIA_VAL}\metadata.level1.parquet",
        backend="MagenticOne",
        workspace=Path(r"D:\myproject\mira-ai-lab\mas-failure-attribution\runs\magentic_workspace"),
        output=Path(r"D:\myproject\mira-ai-lab\mas-failure-attribution\runs\magentic_output"),
        max_samples=1,
        rollout=False,
        skip_existing=False,
        max_rounds=2,
        concurrent=False,
        mode="full",
    )
    # args = _args_gaia_level1
    args = _args_magentic_one_pipeline
    # args = _args_gaia_level2
    # args = _args_gaia_level3
    main(args)