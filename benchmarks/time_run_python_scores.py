import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TimeRunPythonScores:
    timeout = 300.0

    def setup(self) -> None:
        self.script_path = ROOT / "scripts" / "run_python_scores.py"

    def time_run_python_scores(self) -> None:
        subprocess.run(
            [sys.executable, str(self.script_path)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
