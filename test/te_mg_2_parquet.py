"""Standalone GAIA parquet sampler → MagenticOne (shares runtime with ``MagenticOneAdapter``)."""

from __future__ import annotations

import asyncio
import configparser
import json
import os
import random
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List

# Match adapter import order: env + warnings before autogen.
os.environ.setdefault("WANDB_DISABLED", "true")
os.environ.setdefault("WEAVE_DISABLE_AUTO_LOGGING", "true")
warnings.filterwarnings(
    "ignore",
    message='.*Field "model_.*" has conflict with protected namespace.*',
)

from autogen_agentchat.base import TaskResult
from autogen_ext.models.openai import OpenAIChatCompletionClient

from adapter.MagenticOne.core import _build_model_client
from adapter.MagenticOne.magentic_runtime import (
    WINDOWS_TEAM_TASK_PREFIX,
    build_agent_topology,
    build_gaia_agent_task,
    build_system_prompt,
    close_surfer_silently,
    create_magentic_team,
    extract_model_prediction_from_task_result,
    gaia_attachments_root,
    is_transient_run_stream_failure,
    patch_magentic_one_orchestrator_prompts_for_windows,
)

patch_magentic_one_orchestrator_prompts_for_windows()


def _load_config_from_ini():
    """Load ``config.ini`` and populate environment variables."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    config_path = repo_root / "config.ini"
    
    if not config_path.exists():
        print(f"[warn] Config file not found: {config_path}")
        return
    
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')
    
    if 'magentic' not in config:
        print(f"[warn] Config file missing [magentic] section")
        return
    
    magentic = config['magentic']
    
    # API settings
    if magentic.get('api_key'):
        os.environ.setdefault('MAGENTIC_API_KEY', magentic['api_key'])
    
    if magentic.get('base_url'):
        os.environ.setdefault('MAGENTIC_BASE_URL', magentic['base_url'])
    
    if magentic.get('model'):
        os.environ.setdefault('MAGENTIC_MODEL', magentic['model'])
    
    if magentic.get('timeout_sec'):
        os.environ.setdefault('MAGENTIC_TIMEOUT_SEC', magentic['timeout_sec'])
    
    if magentic.get('max_retries'):
        os.environ.setdefault('MAGENTIC_MAX_RETRIES', magentic['max_retries'])
    
    # model_info JSON
    if magentic.get('model_info'):
        os.environ.setdefault('MAGENTIC_MODEL_INFO_JSON', magentic['model_info'])
    
    # GAIA dataset paths
    if magentic.get('gaia_validation_dir'):
        os.environ.setdefault('GAIA_VALIDATION_DIR', magentic['gaia_validation_dir'])
    
    if magentic.get('gaia_attachments_root'):
        os.environ.setdefault('GAIA_ATTACHMENTS_ROOT', magentic['gaia_attachments_root'])
    
    # Run / retry tuning
    if magentic.get('run_max_attempts'):
        os.environ.setdefault('TE_MG2_RUN_MAX_ATTEMPTS', magentic['run_max_attempts'])
    
    if magentic.get('run_retry_base_sec'):
        os.environ.setdefault('TE_MG2_RUN_RETRY_BASE_SEC', magentic['run_retry_base_sec'])
    
    print(f"[config] Loaded settings from {config_path}")


def _require_pandas():
    try:
        import pandas as pd
    except ImportError as e:
        raise SystemExit("Install pandas and pyarrow: pip install pandas pyarrow") from e
    return pd


def _gaia_cell_empty(pd: Any, val: Any) -> bool:
    if val is None:
        return True
    try:
        if pd.isna(val):
            return True
    except Exception:
        pass
    s = str(val).strip()
    return s == "" or s.lower() in ("nan", "none", "<na>")


def _gaia_row_both_files_empty(pd: Any, row: Any) -> bool:
    return _gaia_cell_empty(pd, row.get("file_name")) and _gaia_cell_empty(pd, row.get("file_path"))


def _gaia_row_both_files_nonempty(pd: Any, row: Any) -> bool:
    return (not _gaia_cell_empty(pd, row.get("file_name"))) and (
        not _gaia_cell_empty(pd, row.get("file_path"))
    )


def load_gaia_sample_tasks(
    validation_dir: Path,
    rng: random.Random,
) -> List[Dict[str, Any]]:
    pd = _require_pandas()
    out: List[Dict[str, Any]] = []
    for lev in (1, 2, 3):
        path = validation_dir / f"metadata.level{lev}.parquet"
        if not path.is_file():
            print(f"[warn] Skipping missing file: {path}")
            continue
        df = pd.read_parquet(path)
        empty_mask = df.apply(lambda r: _gaia_row_both_files_empty(pd, r), axis=1)
        full_mask = df.apply(lambda r: _gaia_row_both_files_nonempty(pd, r), axis=1)

        def _pick(mask: Any, kind: str) -> None:
            sub = df[mask]
            if len(sub) == 0:
                print(f"[warn] level{lev}: no rows matching '{kind}' filter, skipping")
                return
            row = sub.sample(1, random_state=rng.randrange(1 << 30)).iloc[0]
            qid = str(row.get("task_id", "")).strip()
            out.append(
                {
                    "question": str(row.get("Question", "")).strip(),
                    "question_ID": qid,
                    "level": str(row.get("Level", "")).strip(),
                    "ground_truth": str(row.get("Final answer", "")).strip(),
                    "file_name": ""
                    if _gaia_cell_empty(pd, row.get("file_name"))
                    else str(row.get("file_name")).strip(),
                    "file_path": ""
                    if _gaia_cell_empty(pd, row.get("file_path"))
                    else str(row.get("file_path")).strip(),
                    "gaia_parquet": path.name,
                    "gaia_sample_kind": kind,
                }
            )

        _pick(empty_mask, "no_attached_file")
        _pick(full_mask, "with_attached_file")
    return out


def _safe_json_filename_part(s: str, max_len: int = 80) -> str:
    t = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in (s or "").strip())
    t = t.strip("_") or "unknown"
    return t[:max_len]


async def _run_single_gaia_sample(
    model_client: OpenAIChatCompletionClient,
    sample: Dict[str, Any],
    *,
    attachments_root: Path,
    run_stream_max_attempts: int,
    run_stream_retry_base_sec: float,
    out_dir: Path,
    sample_index: int,
) -> None:
    question_text = (sample.get("question") or "").strip()
    task = WINDOWS_TEAM_TASK_PREFIX + build_gaia_agent_task(sample, attachments_root)
    question_id = sample["question_ID"]
    level = sample["level"]
    ground_truth = sample["ground_truth"]
    t_start = time.time()

    history: List[Dict[str, Any]] = []
    step_counter = 0
    run_error: str | None = None
    model_prediction = ""
    run_stream_attempts_used = 0

    surfer: Any = None
    file_surfer: Any = None
    coder: Any = None
    terminal: Any = None

    stem = _safe_json_filename_part(question_id)
    exec_workspace = (out_dir / "code_exec" / stem).resolve()
    exec_workspace.mkdir(parents=True, exist_ok=True)

    for attempt in range(run_stream_max_attempts):
        run_stream_attempts_used = attempt + 1
        if attempt > 0:
            print(
                f"\n[retry] Run {run_stream_attempts_used}/{run_stream_max_attempts} "
                f"(new team, task restarted from scratch)..."
            )

        surfer, file_surfer, coder, terminal, team = create_magentic_team(
            model_client,
            exec_workspace,
            include_web=not os.environ.get("MAGENTIC_SKIP_WEB", "").strip().lower()
            in ("1", "true", "yes", "on"),
        )
        history = []
        step_counter = 0
        run_error = None
        model_prediction = ""

        try:
            async for event in team.run_stream(task=task):
                t_end = time.time()
                timestamp = t_end - t_start

                event_content = str(event)
                source = getattr(event, "source", None)

                role = "assistant" if source and source != "user" else "user"
                name = source if source else "unknown"

                history.append(
                    {
                        "step": step_counter,
                        "event_type": type(event).__name__,
                        "content": event_content,
                        "role": role,
                        "name": name,
                        "source": source,
                    }
                )
                step_counter += 1

                if isinstance(event, TaskResult):
                    model_prediction = extract_model_prediction_from_task_result(event)

                print(f"\n[{timestamp:.2f}s] {type(event).__name__}")
                print(f"Source: {source}")
                print(f"Content: {event}\n")

            await close_surfer_silently(surfer)
            break

        except Exception as e:
            await close_surfer_silently(surfer)
            run_error = f"{type(e).__name__}: {e!r}"
            transient = is_transient_run_stream_failure(e)
            print(f"\n[error] {run_error}")
            if transient and attempt + 1 < run_stream_max_attempts:
                delay = run_stream_retry_base_sec * (2**attempt)
                print(f"[retry] Auto-retry in {delay:.1f}s...")
                await asyncio.sleep(delay)
                continue

            if not history:
                print("\n[warn] No history collected; skipping save for this sample.")
                return
            print(f"\n[warn] Collected {len(history)} history entries; writing JSON including run_error.")
            break

    agent_topology = build_agent_topology(history)
    system_prompt = build_system_prompt(
        agent_topology, history, surfer, file_surfer, coder, terminal
    )

    pred_st = model_prediction.strip()
    gt_st = ground_truth.strip()
    is_correct = (pred_st == gt_st) if gt_st else True

    result: Dict[str, Any] = {
        "is_correct": is_correct,
        "question": question_text,
        "agent_task": task,
        "question_ID": question_id,
        "level": level,
        "ground_truth": ground_truth,
        "history": history,
        "model_prediction": model_prediction,
        "system_prompt": system_prompt,
        "agent_topology": agent_topology,
        "run_error": run_error,
        "run_stream_attempts_used": run_stream_attempts_used,
        "gaia_parquet": sample.get("gaia_parquet"),
        "gaia_sample_kind": sample.get("gaia_sample_kind"),
        "file_name": sample.get("file_name"),
        "file_path": sample.get("file_path"),
    }

    kind = _safe_json_filename_part(str(sample.get("gaia_sample_kind", "kind")), 40)
    output_path = out_dir / f"gaia_{sample_index:02d}_{stem}_{kind}_{time.time_ns()}.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"[ok] Result saved to {output_path}")


async def main() -> None:
    repo_root = Path(__file__).resolve().parent
    validation_dir = Path(
        os.environ.get(
            "GAIA_VALIDATION_DIR",
            str(repo_root / "dataset" / "gaia_dataset_raw" / "2023" / "validation"),
        )
    )
    rng_seed = os.environ.get("GAIA_SAMPLE_SEED")
    rng = random.Random(
        int(rng_seed) if rng_seed and rng_seed.isdigit() else int(time.time()) ^ (os.getpid() << 16)
    )
    samples = load_gaia_sample_tasks(validation_dir, rng)
    if not samples:
        print(
            "[fatal] No GAIA samples drawn; ensure parquet files exist and columns include "
            "Question / task_id / Level / Final answer / file_name / file_path."
        )
        return

    model_client = _build_model_client()

    run_stream_max_attempts = int(os.environ.get("TE_MG2_RUN_MAX_ATTEMPTS", "5"))
    run_stream_retry_base_sec = float(os.environ.get("TE_MG2_RUN_RETRY_BASE_SEC", "10"))
    out_dir = repo_root / "workspace" / "exp_out"
    attachments_root = gaia_attachments_root(repo_root)
    print(f"[GAIA] attachments_root={attachments_root}")

    print(f"[GAIA] {len(samples)} sample(s) total.")
    for i, sample in enumerate(samples):
        print(
            f"\n{'=' * 60}\n[GAIA] Sample {i + 1}/{len(samples)} "
            f"task_id={sample.get('question_ID')} kind={sample.get('gaia_sample_kind')}\n{'=' * 60}"
        )
        await _run_single_gaia_sample(
            model_client,
            sample,
            attachments_root=attachments_root,
            run_stream_max_attempts=run_stream_max_attempts,
            run_stream_retry_base_sec=run_stream_retry_base_sec,
            out_dir=out_dir,
            sample_index=i,
        )

    try:
        await model_client.close()
    except Exception:
        pass


if __name__ == "__main__":
    # Load optional config.ini overrides.
    _load_config_from_ini()
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
