"""
最小复现：空 model_prediction（空 solution.py）在本地 pytest 下必然失败；
若远程 eval 仍记为 true，原因在 sandbox / run_code 的判定，而非本项目内的真值表逻辑。

用法（在仓库根目录）:
  python scripts/repro_empty_model_prediction.py
  python scripts/repro_empty_model_prediction.py --log path/to/log.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def default_log_path() -> Path:
    repo = Path(__file__).resolve().parents[1]
    return repo / "output" / "kodcode" / "round_1" / "Algorithm_1665_I" / "log.json"


def run_local_pytest_empty_solution(test_code: str) -> int:
    """与 eval 一致：仅提交空 solution.py + 数据集里的 test 字符串，在本地跑 pytest。"""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "solution.py").write_text("", encoding="utf-8")
        test_file = root / "test_task.py"
        test_file.write_text(test_code, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-q"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        return proc.returncode


def repro_none_result_crash() -> None:
    """eval.run_correctness_eval_task 在 code_exec 返回 None 时会崩，与「误判为 true」无关。"""
    print("\n--- 附加：code_exec -> None 时，若直接访问 result.status 会 AttributeError ---")
    result = None
    try:
        _ = result.status
    except AttributeError as e:
        print("预期异常:", e)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=None, help="含 test 字段的 log.json")
    args = parser.parse_args()
    log_path = args.log or default_log_path()
    if not log_path.is_file():
        print(f"找不到 log: {log_path}")
        sys.exit(1)

    data = json.loads(log_path.read_text(encoding="utf-8"))
    pred = data.get("model_prediction", "<missing>")
    test = data["test"]
    print(f"log: {log_path}")
    print(f"model_prediction 长度: {len(pred) if isinstance(pred, str) else 'n/a'}")

    code = run_local_pytest_empty_solution(test)
    print(f"本地 pytest（空 solution.py）退出码: {code}")
    print("说明: 退出码 0 才表示 pytest 成功；2 一般为收集阶段错误（如此处的 ImportError）。")
    if code == 0:
        print("警告: 本地空提交居然通过 —— 请检查环境与 test 内容。")
    else:
        print(
            "结论: 在本机标准 pytest 下，空 solution 不可能判为通过。\n"
            "若 eval_kodcode.json 里同一题号为 true，只能说明当时 run_code/沙箱对\n"
            "「pytest 收集失败」类输出仍报了 RunStatus.Success，或结果与当前 log 不一致。\n"
            "请在可连沙箱的环境对 run_code 响应打印 status/message 做对照。"
        )

    repro_none_result_crash()


if __name__ == "__main__":
    main()
