#!/usr/bin/env python3
"""Convert CSV layer files to Parquet format with round-trip verification."""

from pathlib import Path

import pandas as pd
import polars as pl

# Define paths
CSV_DIR = Path("data/layers/csv")
PARQUET_DIR = Path("data/layers/parquet")

# Ensure parquet directory exists
PARQUET_DIR.mkdir(parents=True, exist_ok=True)


def convert_and_verify(csv_path: Path) -> tuple[bool, str]:
    """
    Convert a single CSV file to Parquet and verify round-trip.

    Args:
        csv_path: Path to CSV file

    Returns:
        (success, message) tuple
    """
    try:
        # Read CSV with polars, using null_values=["NA"] for consistency
        df_pl = pl.read_csv(csv_path, null_values=["NA"])

        # Define parquet output path
        parquet_path = PARQUET_DIR / csv_path.stem
        parquet_path = parquet_path.with_suffix(".parquet")

        # Write to parquet with default snappy compression
        df_pl.write_parquet(parquet_path)

        # Round-trip verification
        df_pl_roundtrip = pl.read_parquet(parquet_path)
        df_pd_original = pl.read_csv(csv_path, null_values=["NA"]).to_pandas()
        df_pd_roundtrip = df_pl_roundtrip.to_pandas()

        # Use pandas assert to verify equality
        pd.testing.assert_frame_equal(df_pd_roundtrip, df_pd_original)

        return True, f"✓ {csv_path.name}"

    except Exception as e:
        return False, f"✗ {csv_path.name}: {str(e)}"


def main() -> int:
    """Main conversion workflow."""
    print(f"Converting CSV files from {CSV_DIR} to {PARQUET_DIR}...\n")

    # Find all CSV files
    csv_files = sorted(CSV_DIR.glob("*.csv"))

    if not csv_files:
        print(f"No CSV files found in {CSV_DIR}")
        return 1

    print(f"Found {len(csv_files)} CSV files to convert\n")

    converted = 0
    verified = 0
    failures = []

    for i, csv_path in enumerate(csv_files, 1):
        success, message = convert_and_verify(csv_path)

        if success:
            converted += 1
            verified += 1
        else:
            converted += 1
            failures.append(message)

        # Progress indicator
        if i % 50 == 0:
            print(f"  Processed {i}/{len(csv_files)}")

    print("\n" + "=" * 60)
    print("Conversion Summary:")
    print(f"  Total CSV files: {len(csv_files)}")
    print(f"  Converted: {converted}")
    print(f"  Verified: {verified}")

    if failures:
        print(f"\n  Failures ({len(failures)}):")
        for failure in failures:
            print(f"    {failure}")
        print(f"{'=' * 60}\n")
        return 1

    # Verify file count
    parquet_files = list(PARQUET_DIR.glob("*.parquet"))
    print(f"  Parquet files created: {len(parquet_files)}")
    print(f"{'=' * 60}\n")

    if len(parquet_files) != len(csv_files):
        print(
            f"ERROR: Parquet file count ({len(parquet_files)}) "
            f"does not match CSV count ({len(csv_files)})"
        )
        return 1

    print("✓ All conversions successful and verified!\n")
    return 0


if __name__ == "__main__":
    exit(main())
