#!/usr/bin/env python3
"""
Integration Test Orchestrator

Orchestrates the integration test workflow for OHI calculations.
Supports running setup, and generates JSON summary reports.

Usage:
    python tests/scripts/run_integration_tests.py --setup --noise-levels 0,0.01,0.05
    python tests/scripts/run_integration_tests.py --output-dir tests/results
    python tests/scripts/run_integration_tests.py --noise-levels 0.01
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_noise_levels(noise_str: str) -> list[float]:
    levels = []
    for level in noise_str.split(","):
        level = level.strip()
        if level:
            levels.append(float(level))
    return levels


def check_docker_available() -> bool:
    return shutil.which("docker") is not None


def run_setup(project_root: Path) -> int:
    setup_script = project_root / "tests" / "scripts" / "setup_test_data.py"
    if not setup_script.exists():
        print(f"ERROR: Setup script not found at {setup_script}")
        return 1

    print("\n" + "=" * 70)
    print("Running setup_test_data.py...")
    print("=" * 70)

    result = subprocess.run(
        [sys.executable, str(setup_script)],
        cwd=str(project_root),
        capture_output=False,
    )

    return result.returncode


def run_pytest(project_root: Path, output_dir: Path) -> dict[str, Any]:
    print("\n  Running pytest on tests/integration/...")

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/integration/",
        "-v",
        "--tb=short",
        f"--junitxml={output_dir / 'junit.xml'}",
    ]

    env = os.environ.copy()
    env["OHI_TEST_OUTPUT_DIR"] = str(output_dir)

    result = subprocess.run(
        pytest_cmd,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        env=env,
    )

    output = result.stdout + result.stderr
    passed, failed, skipped = parse_pytest_results(output)

    status = "PASS" if result.returncode == 0 and failed == 0 else "FAIL"

    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "status": status,
        "returncode": result.returncode,
        "output": output,
    }


def parse_pytest_results(output: str) -> tuple[int, int, int]:
    passed = 0
    failed = 0
    skipped = 0

    passed_match = re.search(r"(\d+)\s+passed", output)
    if passed_match:
        passed = int(passed_match.group(1))

    failed_match = re.search(r"(\d+)\s+failed", output)
    if failed_match:
        failed = int(failed_match.group(1))

    error_match = re.search(r"(\d+)\s+error", output)
    if error_match:
        failed += int(error_match.group(1))

    skipped_match = re.search(r"(\d+)\s+skipped", output)
    if skipped_match:
        skipped = int(skipped_match.group(1))

    return passed, failed, skipped


def generate_summary_report(
    output_dir: Path,
    noise_levels: list[float],
    result: dict[str, Any],
) -> dict[str, Any]:
    overall_status = "PASS" if result["failed"] == 0 else "FAIL"

    results_list = [
        {
            "noise_level": nl,
            "passed": result["passed"],
            "failed": result["failed"],
            "status": result["status"],
        }
        for nl in noise_levels
    ]

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "noise_levels": noise_levels,
        "results": results_list,
        "overall_status": overall_status,
        "total_passed": result["passed"],
        "total_failed": result["failed"],
    }

    report_path = output_dir / "integration_summary.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Summary report written to: {report_path}")

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orchestrate integration tests for OHI calculations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python tests/scripts/run_integration_tests.py --setup --noise-levels 0,0.01,0.05
    python tests/scripts/run_integration_tests.py --output-dir tests/results
    python tests/scripts/run_integration_tests.py --noise-levels 0.01
        """,
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run setup_test_data.py before running tests",
    )
    parser.add_argument(
        "--noise-levels",
        type=str,
        default="0",
        help="Comma-separated noise levels to test (default: 0)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="tests/output",
        help="Directory for test output and reports (default: tests/output)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent.parent
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    noise_levels = parse_noise_levels(args.noise_levels)
    docker_available = check_docker_available()

    print("=" * 70)
    print("OHI Integration Test Orchestrator")
    print("=" * 70)
    print(f"Project root: {project_root}")
    print(f"Output directory: {output_dir}")
    print(f"Noise levels: {noise_levels}")
    print(f"Docker available: {docker_available}")
    print(f"Run setup: {args.setup}")
    print("=" * 70)

    if args.setup:
        setup_result = run_setup(project_root)
        if setup_result != 0:
            print("\nERROR: Setup failed, aborting tests")
            return 1
        print("\nSetup completed successfully")

    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print("Running Integration Tests")
    print("=" * 70)

    if not docker_available:
        print("\n  NOTE: Docker not available - R-dependent tests will be skipped")

    result = run_pytest(project_root, output_dir)

    status_icon = "[PASS]" if result["status"] == "PASS" else "[FAIL]"
    print(
        f"\n  {status_icon} Tests completed: {result['passed']} passed, "
        f"{result['failed']} failed, {result['skipped']} skipped"
    )

    print("\n" + "=" * 70)
    print("Generating Summary Report")
    print("=" * 70)

    summary = generate_summary_report(output_dir, noise_levels, result)

    print("\n" + "=" * 70)
    print("Final Summary")
    print("=" * 70)
    print(f"Overall status: {summary['overall_status']}")
    print(f"Total passed: {summary['total_passed']}")
    print(f"Total failed: {summary['total_failed']}")
    print("=" * 70)

    return 0 if summary["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
