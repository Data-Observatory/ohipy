#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class BranchTiming:
    branch: str
    commit: str
    iterations: int
    warmups: int
    mean: float
    std: float
    minimum: float
    maximum: float
    median: float
    total: float
    runs: list[float]


def _run(cmd: list[str], cwd: Path, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    if quiet:
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)


def _get_commit(worktree: Path) -> str:
    result = _run(["git", "rev-parse", "--short", "HEAD"], cwd=worktree)
    return result.stdout.strip()


def _setup_worktree(repo_root: Path, parent: Path, branch: str) -> Path:
    worktree = parent / f"wt-{branch}"
    _run(["git", "worktree", "add", "--detach", str(worktree), branch], cwd=repo_root)
    return worktree


def _ensure_chl_data(repo_root: Path, worktree: Path) -> None:
    # Check if data/ directory exists in the worktree (opt2, newer branches)
    target_data = worktree / "data" / "conf" / "goals.csv"
    if target_data.exists():
        return

    # Fallback to chl/ symlink for old branches (main, opt1)
    source_chl = repo_root / "chl"
    target_chl = worktree / "chl"
    required = target_chl / "comunas" / "conf" / "goals.csv"

    if required.exists():
        return

    if target_chl.exists() or target_chl.is_symlink():
        if target_chl.is_symlink() or target_chl.is_file():
            target_chl.unlink()
        else:
            shutil.rmtree(target_chl)

    try:
        os.symlink(source_chl, target_chl, target_is_directory=True)
    except OSError:
        shutil.copytree(source_chl, target_chl)


def _remove_worktree(repo_root: Path, worktree: Path) -> None:
    _run(["git", "worktree", "remove", "--force", str(worktree)], cwd=repo_root, quiet=True)


def _time_run_python_scores(worktree: Path, warmups: int, iterations: int) -> list[float]:
    _run(["uv", "sync"], cwd=worktree, quiet=True)
    venv_python = worktree / ".venv" / "bin" / "python"
    _run(
        ["uv", "pip", "install", "--python", str(venv_python), "polars", "pyarrow"],
        cwd=worktree,
        quiet=True,
    )

    for _ in range(warmups):
        try:
            _run(["uv", "run", "python", "scripts/run_python_scores.py"], cwd=worktree, quiet=True)
        except subprocess.CalledProcessError:
            subprocess.run(
                ["uv", "run", "python", "scripts/run_python_scores.py"],
                cwd=worktree,
                check=False,
                text=True,
            )
            raise

    runs: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        try:
            _run(["uv", "run", "python", "scripts/run_python_scores.py"], cwd=worktree, quiet=True)
        except subprocess.CalledProcessError:
            subprocess.run(
                ["uv", "run", "python", "scripts/run_python_scores.py"],
                cwd=worktree,
                check=False,
                text=True,
            )
            raise
        end = time.perf_counter()
        runs.append(end - start)
    return runs


def _summarize(branch: str, commit: str, warmups: int, runs: list[float]) -> BranchTiming:
    return BranchTiming(
        branch=branch,
        commit=commit,
        iterations=len(runs),
        warmups=warmups,
        mean=statistics.mean(runs),
        std=statistics.stdev(runs) if len(runs) > 1 else 0.0,
        minimum=min(runs),
        maximum=max(runs),
        median=statistics.median(runs),
        total=sum(runs),
        runs=runs,
    )


def _print_summary(results: list[BranchTiming]) -> None:
    fastest = min(results, key=lambda x: x.mean).mean
    header = (
        "| Branch | Commit | Mean (s) | Std (s) | Min (s) | Max (s) | "
        "Median (s) | Speedup vs fastest |"
    )

    print("\n## Cross-Branch Timing Summary")
    print(header)
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in sorted(results, key=lambda x: x.mean):
        speedup = row.mean / fastest
        print(
            f"| {row.branch} | {row.commit} | {row.mean:.3f} | {row.std:.3f} | "
            f"{row.minimum:.3f} | {row.maximum:.3f} | {row.median:.3f} | {speedup:.2f}x |"
        )


def _write_json(
    repo_root: Path, results: list[BranchTiming], warmups: int, iterations: int
) -> Path:
    out_dir = repo_root / "comparative"
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"branch_benchmark_{timestamp}.json"

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "script": "scripts/run_python_scores.py",
        "warmups": warmups,
        "iterations": iterations,
        "results": [asdict(r) for r in results],
    }

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark scripts/run_python_scores.py across git branches."
    )
    parser.add_argument(
        "--branches",
        nargs="+",
        default=["main", "opt1", "opt2"],
        help="Branches to benchmark (default: main opt1 opt2)",
    )
    parser.add_argument("--iterations", type=int, default=3, help="Measured runs per branch")
    parser.add_argument("--warmups", type=int, default=1, help="Warmup runs per branch")
    args = parser.parse_args()

    if args.iterations < 1:
        raise ValueError("--iterations must be >= 1")
    if args.warmups < 0:
        raise ValueError("--warmups must be >= 0")

    repo_root = Path(__file__).resolve().parent.parent
    temp_parent = Path(tempfile.mkdtemp(prefix="ohipy-branch-bench-"))

    results: list[BranchTiming] = []
    try:
        for branch in args.branches:
            print(f"\n=== Benchmarking {branch} ===")
            worktree = _setup_worktree(repo_root, temp_parent, branch)
            try:
                _ensure_chl_data(repo_root, worktree)
                commit = _get_commit(worktree)
                runs = _time_run_python_scores(worktree, args.warmups, args.iterations)
                summary = _summarize(branch=branch, commit=commit, warmups=args.warmups, runs=runs)
                results.append(summary)
                print(
                    f"{branch} ({commit}) -> mean={summary.mean:.3f}s, "
                    f"min={summary.minimum:.3f}s, max={summary.maximum:.3f}s"
                )
            finally:
                _remove_worktree(repo_root, worktree)
    finally:
        shutil.rmtree(temp_parent, ignore_errors=True)

    _print_summary(results)
    output = _write_json(repo_root, results, args.warmups, args.iterations)
    print(f"\nSaved JSON results: {output}")


if __name__ == "__main__":
    main()
