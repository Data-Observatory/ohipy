"""Run calculate_all and write scores to comparative/scores_2024_py.csv."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ohipy.calculate_all import calculate_all
from ohipy.config import load_config
from ohipy.layers import load_layers

scores = calculate_all(load_config(), load_layers(load_config()))
scores.to_csv("../comparative/scores_2024_py.csv", index=False)
