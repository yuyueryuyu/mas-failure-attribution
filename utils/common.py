"""Shared serialization and result-shaping helpers used across the project."""

from functools import partial
import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel
from pydantic_core import to_jsonable_python


def dumps(model: BaseModel | Iterable[BaseModel]):
    """Convert one or many Pydantic models into JSON-serializable Python objects."""
    if isinstance(model, BaseModel):
        return model.model_dump()
    else:
        return [m.model_dump() for m in model]

def read_json_file(json_file: Path, encoding: str = "utf-8"):
    """Read and parse a JSON file with basic error handling."""
    if not json_file.exists():
        raise FileNotFoundError(f"json_file: {json_file} not exist")

    with open(json_file, "r", encoding=encoding) as fin:
        try:
            data = json.load(fin)
        except Exception:
            raise ValueError(f"read json file: {json_file} failed")
    return data

def write_json_file(json_file: Path, data: Any, encoding: str = "utf-8", indent: int = 4, use_fallback: bool = False):
    """Write JSON data to disk and create parent directories when missing."""
    folder_path = json_file.parent
    if not folder_path.exists():
        folder_path.mkdir(parents=True, exist_ok=True)

    custom_default = to_jsonable_python

    with open(json_file, "w", encoding=encoding) as fout:
        json.dump(data, fout, ensure_ascii=False, indent=indent, default=custom_default)

def match_info(attack_info: list, diagnose_info: list):
    """Compare two attribution chains by step/fault pairs."""
    attack_info = [(info['step_id'], info['fault_code']) for info in attack_info]
    diagnose_info = [(info['step_id'], info['fault_code']) for info in diagnose_info]
    return attack_info == diagnose_info

def save_final_result(path: Path, log: dict, info: list):
    """Assemble and persist final attribution result for one task."""
    id = log['question_ID']
    log['mistake_information'] = info
    log['attribution_subgraph'] = {
        'nodes': [],
        'edges': {}
    }
    for i in info:
        step = i['step_id']
        i['mistake_agent'] = log['history'][step-1]['name']
        if step not in log['attribution_subgraph']['nodes']:
            log['attribution_subgraph']['nodes'].append(step)
        for e in  i['related_error']:
            edges = log['attribution_subgraph']['edges'].setdefault(step, [])
            if e not in log['attribution_subgraph']['nodes']:
                log['attribution_subgraph']['nodes'].append(e)            
            if e not in edges:
                edges.append(e)

    write_json_file(path / f'{id}.json', log)
    
