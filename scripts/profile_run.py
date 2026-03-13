"""Profile the OHI calculation pipeline with cProfile.

This script profiles the full pipeline (load_config → load_layers → calculate_all)
and outputs timing data with the top 30 functions by cumulative time.
"""

import cProfile
import pstats
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ohipy.calculate_all import calculate_all
from ohipy.config import load_config
from ohipy.layers import load_layers


def main():
    """Profile the full OHI calculation pipeline."""
    # Initialize profiler
    pr = cProfile.Profile()

    # Profile the pipeline
    pr.enable()

    config = load_config()
    layers = load_layers(config)
    scores = calculate_all(config, layers)

    pr.disable()

    # Sort and print top 30 functions by cumulative time
    stats = pstats.Stats(pr)
    stats.sort_stats("cumulative").print_stats(30)

    # Save output to evidence file
    output_file = Path(".sisyphus/evidence/task-1-profile-output.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        stats = pstats.Stats(pr, stream=f)
        stats.sort_stats("cumulative").print_stats(30)

    print(f"\nProfile output saved to: {output_file}")


if __name__ == "__main__":
    main()
