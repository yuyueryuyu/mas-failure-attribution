from functools import partial
import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel
from pydantic_core import to_jsonable_python


def dumps(model: BaseModel | Iterable[BaseModel]):
    if isinstance(model, BaseModel):
        return model.model_dump()
    else:
        return [m.model_dump() for m in model]

def read_json_file(json_file: Path, encoding: str = "utf-8") -> list[Any]:
    if not json_file.exists():
        raise FileNotFoundError(f"json_file: {json_file} not exist, return []")

    with open(json_file, "r", encoding=encoding) as fin:
        try:
            data = json.load(fin)
        except Exception:
            raise ValueError(f"read json file: {json_file} failed")
    return data

def write_json_file(json_file: Path, data: Any, encoding: str = "utf-8", indent: int = 4, use_fallback: bool = False):
    folder_path = json_file.parent
    if not folder_path.exists():
        folder_path.mkdir(parents=True, exist_ok=True)

    custom_default = to_jsonable_python

    with open(json_file, "w", encoding=encoding) as fout:
        json.dump(data, fout, ensure_ascii=False, indent=indent, default=custom_default)