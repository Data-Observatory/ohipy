import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class TimeRunPythonScores:
    timeout = 300.0

    def setup(self) -> None:
        from ohipy.config import load_config
        from ohipy.layers import load_layers

        self._calculate_all = __import__(
            "ohipy.calculate_all", fromlist=["calculate_all"]
        ).calculate_all
        self.config = load_config()
        self.layers = load_layers(self.config)

    def time_calculate_all_pipeline(self) -> None:
        self._calculate_all(self.config, self.layers)
