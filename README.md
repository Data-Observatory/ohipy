# OHI Python Validation

## Quick Start

### Validate All Goals
```bash
cd python
uv run python validate_goals.py
```

### Validate Specific Goal(s)
```bash
# Single goal
uv run python validate_goals.py FIS

# Multiple goals
uv run python validate_goals.py FIS MAR CW

# With verbose output (shows mismatches)
uv run python validate_goals.py CW --verbose
```

### List Available Goals
```bash
uv run python validate_goals.py --list
```

## Available Goals

All 14 pre-index goals are implemented and validated:
- FIS (Fisheries)
- MAR (Mariculture)
- AO (Artisanal Opportunities)
- NP (Natural Products)
- CS (Carbon Sequestration)
- CP (Coastal Protection)
- TR (Tourism & Recreation)
- LIV (Livelihoods)
- ECO (Economies)
- ICO (Iconic Species)
- LSP (Lasting Special Places)
- CW (Clean Waters)
- HAB (Habitats)
- SPP (Species)

## Validation Criteria

- **Match rate**: ≥99% of values within tolerance
- **Max difference**: <0.01 (absolute)
- **Tolerance**: `np.allclose(rtol=0, atol=0.01)`

## Output Format

```
Goal   Status   Match %    Max Diff     Status %   Trend %
----------------------------------------------------------
FIS    ✓ PASS   100.0%     0.004951     100.0%     100.0%
MAR    ✓ PASS   100.0%     0.000000     100.0%     100.0%
...
```

## Comprehensive Testing

For detailed testing with all goals:
```bash
uv run python test_all_goals.py
```

This provides more detailed output including per-dimension breakdowns.

## End-to-End Parity (R vs Python)

### 1) Generate R reference scores

From the project root:

```bash
Rscript comparative/calculate_scores.r
```

This produces `comparative/scores_2024_r.csv`.

### 2) Generate Python scores

```bash
cd python
uv run python -c "from ohi.config import load_config; from ohi.layers import load_layers; from ohi.calculate_all import calculate_all; scores = calculate_all(load_config(), load_layers(load_config())); scores.to_csv('../comparative/scores_2024_py.csv', index=False)"
```

### 3) Compare outputs (authoritative gate)

```bash
cd ..
uv run python comparative/compare_scores.py
```

The comparison script writes `comparative/scores_difference.csv` and is the single source of truth for pass/fail.

## Optional: Fixture-based Validation

If you want intermediate checkpoints for debugging:

```bash
Rscript comparative/generate_test_fixtures.r
uv run python comparative/validate_fixtures.py --list
```

See `comparative/QUICKSTART.md` for the full fixture workflow.
