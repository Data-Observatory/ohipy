#!/usr/bin/env python3
"""OHI Performance Benchmark - Measures execution time of calculate_all().

This script provides a reliable and reproducible timing harness for measuring
the performance of the OHI calculation pipeline. It runs the calculation
multiple times and provides statistical analysis of the timing results.
"""

import sys
import time
import statistics
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from ohipy.config import load_config
from ohipy.layers import load_layers
from ohipy.calculate_all import calculate_all


def run_benchmark(iterations=5):
    """
    Run calculate_all() multiple times and measure execution time.

    Args:
        iterations: Number of times to run calculate_all() (default: 5)

    Returns:
        dict: Timing statistics (mean, std, min, max, median) in seconds
    """
    print(f"OHI Performance Benchmark")
    print(f"Running calculate_all() {iterations} times...\n")

    # Load config and layers once (not timed)
    print("Loading configuration and data layers...")
    config = load_config()
    layers = load_layers(config)
    print("Configuration and layers loaded.\n")

    # Run benchmark iterations
    times = []
    for i in range(1, iterations + 1):
        print(f"Iteration {i}/{iterations}...", end=" ", flush=True)
        start_time = time.perf_counter()

        # Run the calculation
        scores = calculate_all(config, layers)

        end_time = time.perf_counter()
        elapsed = end_time - start_time
        times.append(elapsed)

        print(f"{elapsed:.3f} seconds")

    # Calculate statistics
    stats = {
        "mean": statistics.mean(times),
        "std": statistics.stdev(times) if len(times) > 1 else 0.0,
        "min": min(times),
        "max": max(times),
        "median": statistics.median(times),
        "iterations": iterations,
        "total_time": sum(times),
    }

    # Print results
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Iterations:    {stats['iterations']}")
    print(f"Total time:    {stats['total_time']:.3f} seconds")
    print(f"Mean:          {stats['mean']:.3f} seconds")
    print(f"Std dev:       {stats['std']:.3f} seconds")
    print(f"Min:           {stats['min']:.3f} seconds")
    print(f"Max:           {stats['max']:.3f} seconds")
    print(f"Median:        {stats['median']:.3f} seconds")
    print("=" * 60)

    return stats


if __name__ == "__main__":
    # Run benchmark with 5 iterations (can be changed via command line arg)
    iterations = 5
    if len(sys.argv) > 1:
        try:
            iterations = int(sys.argv[1])
        except ValueError:
            print(f"Warning: Invalid iterations argument, using default ({iterations})")

    run_benchmark(iterations)
